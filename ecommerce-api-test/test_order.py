"""
订单链路测试 —— 30 条用例，分 6 类场景

设计思路（面试讲法）：
  正常流：下单成功 → 库存扣减 → 金额计算 → 订单可查
  异常流：未登录 / 商品不存在 / 数量非法 / 库存不足
  边界值：满减门槛 500 的临界（499.99? 500? 500.01?）
  并发场景：库存 5 件，10 个用户同时抢，只能成功 5 个
  幂等场景：同一请求重复提交，只能生成一笔订单
"""
import concurrent.futures

import pytest
import requests


# ========== 1. 登录鉴权 ==========

@pytest.mark.parametrize("username,password,expect_code", [
    ("test01", "123456", 200),      # 正常登录
    ("test02", "abc123", 200),      # 另一个账号
    ("test01", "wrong", 401),       # 密码错误
    ("nobody", "123456", 401),      # 用户不存在
    ("", "", 401),                  # 空值
])
def test_login(base_url, username, password, expect_code):
    r = requests.post(f"{base_url}/api/login",
                      json={"username": username, "password": password}, timeout=5)
    assert r.status_code == expect_code


def test_order_without_token(base_url):
    """未登录下单应被拒绝——这是最基础的安全校验"""
    r = requests.post(f"{base_url}/api/orders",
                      json={"product_id": 1, "quantity": 1}, timeout=5)
    assert r.status_code == 401


def test_order_with_fake_token(base_url):
    r = requests.post(f"{base_url}/api/orders",
                      headers={"Authorization": "Bearer fake_token_123"},
                      json={"product_id": 1, "quantity": 1}, timeout=5)
    assert r.status_code == 401


# ========== 2. 下单正常流 ==========

def test_create_order_success(base_url, auth_headers):
    r = requests.post(f"{base_url}/api/orders", headers=auth_headers,
                      json={"product_id": 1, "quantity": 2}, timeout=5)
    assert r.status_code == 201
    data = r.json()["data"]
    assert data["product_id"] == 1
    assert data["quantity"] == 2
    assert data["status"] == "PAID"


def test_stock_deducted_after_order(base_url, auth_headers):
    """下单后库存必须减少——库存账实不符是电商最严重的 bug 之一"""
    before = requests.get(f"{base_url}/api/products", timeout=5).json()["data"]
    stock_before = next(p["stock"] for p in before if p["id"] == 1)

    requests.post(f"{base_url}/api/orders", headers=auth_headers,
                  json={"product_id": 1, "quantity": 3}, timeout=5)

    after = requests.get(f"{base_url}/api/products", timeout=5).json()["data"]
    stock_after = next(p["stock"] for p in after if p["id"] == 1)
    assert stock_after == stock_before - 3


def test_order_queryable(base_url, auth_headers):
    """下单后能用订单号查回详情"""
    created = requests.post(f"{base_url}/api/orders", headers=auth_headers,
                            json={"product_id": 2, "quantity": 1}, timeout=5).json()["data"]
    r = requests.get(f"{base_url}/api/orders/{created['order_id']}", timeout=5)
    assert r.status_code == 200
    assert r.json()["data"]["order_id"] == created["order_id"]


def test_query_not_exist_order(base_url):
    r = requests.get(f"{base_url}/api/orders/ORD_NOT_EXIST", timeout=5)
    assert r.status_code == 404


# ========== 3. 异常流：参数校验 ==========

@pytest.mark.parametrize("quantity", [0, -1, -100])
def test_invalid_quantity(base_url, auth_headers, quantity):
    r = requests.post(f"{base_url}/api/orders", headers=auth_headers,
                      json={"product_id": 1, "quantity": quantity}, timeout=5)
    assert r.status_code == 400


def test_not_exist_product(base_url, auth_headers):
    r = requests.post(f"{base_url}/api/orders", headers=auth_headers,
                      json={"product_id": 9999, "quantity": 1}, timeout=5)
    assert r.status_code == 404


def test_order_exceed_stock(base_url, auth_headers):
    """库存 5 件，买 6 件必须被拒"""
    r = requests.post(f"{base_url}/api/orders", headers=auth_headers,
                      json={"product_id": 2, "quantity": 6}, timeout=5)
    assert r.status_code == 400
    assert "库存" in r.json()["msg"]


# ========== 4. 边界值：满减门槛 ==========
# 规则：满 500 减 50。关键要看「正好 500」算不算满。
# 头戴耳机 250 元，买 2 件 = 正好 500，按规则应减 50 → 实付 450

def test_full_reduction_exact_500(base_url, auth_headers):
    """【关键边界】正好 500 元应触发满减——这里能抓出 >= 写成 > 的差一错误"""
    r = requests.post(f"{base_url}/api/orders", headers=auth_headers,
                      json={"product_id": 4, "quantity": 2}, timeout=5)
    assert r.json()["data"]["amount"] == 450.0, \
        f"正好 500 元应减 50 后为 450，实际 {r.json()['data']['amount']}"


def test_full_reduction_below_threshold(base_url, auth_headers):
    """499 元不满 500，不减"""
    # 无线鼠标 99 元 x 5 = 495，不满 500
    r = requests.post(f"{base_url}/api/orders", headers=auth_headers,
                      json={"product_id": 2, "quantity": 5}, timeout=5)
    assert r.json()["data"]["amount"] == 495.0


def test_full_reduction_above_threshold(base_url, auth_headers):
    """598 元满 500，减 50 → 548"""
    r = requests.post(f"{base_url}/api/orders", headers=auth_headers,
                      json={"product_id": 1, "quantity": 2}, timeout=5)
    assert r.json()["data"]["amount"] == 548.0


# ========== 5. 并发场景：超卖 ==========

def test_concurrent_oversell(base_url, token):
    """
    【核心用例】商品 2 库存 5 件，10 个请求同时抢 1 件。
    正确结果：只能成功 5 单，库存归 0，不能变成负数。
    这里能抓出「先查后扣、未加锁」的竞态缺陷。
    """
    headers = {"Authorization": f"Bearer {token}"}

    def buy_one(_):
        return requests.post(f"{base_url}/api/orders", headers=headers,
                             json={"product_id": 2, "quantity": 1}, timeout=10).status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        codes = list(pool.map(buy_one, range(10)))

    success = codes.count(201)
    stock = next(p["stock"] for p in requests.get(f"{base_url}/api/products", timeout=5).json()["data"]
                 if p["id"] == 2)

    assert success == 5, f"库存 5 件却成功下单 {success} 单，发生超卖"
    assert stock == 0, f"卖完 5 件后库存应为 0，实际 {stock}"


# ========== 6. 幂等：重复提交 ==========

def test_idempotent_submit(base_url, auth_headers):
    """
    【核心用例】同一个 request_id 提交两次（用户手抖连点 / 网络重试），
    只能生成一笔订单，否则用户被重复扣款。
    """
    payload = {"product_id": 1, "quantity": 1, "request_id": "REQ_IDEMPOTENT_001"}

    r1 = requests.post(f"{base_url}/api/orders", headers=auth_headers, json=payload, timeout=5)
    r2 = requests.post(f"{base_url}/api/orders", headers=auth_headers, json=payload, timeout=5)

    assert r1.json()["data"]["order_id"] == r2.json()["data"]["order_id"], \
        f"同一请求生成了两笔订单：{r1.json()['data']['order_id']} / {r2.json()['data']['order_id']}"

    stock = next(p["stock"] for p in requests.get(f"{base_url}/api/products", timeout=5).json()["data"]
                 if p["id"] == 1)
    assert stock == 9, f"只买 1 件，库存应从 10 减到 9，实际 {stock}"
