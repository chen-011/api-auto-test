"""
电商订单服务（被测系统）
用 Python 标准库实现，零第三方依赖，双击即可运行。

接口清单：
  POST /api/login            登录，返回 token
  GET  /api/products         商品列表
  POST /api/orders           下单（需带 token）
  GET  /api/orders/{id}      订单详情
  POST /api/admin/reset      重置数据（测试专用）

注意：本服务故意保留了 3 个电商系统典型缺陷，用于演示
"设计用例 → 发现缺陷 → 定位原因 → 修复回归"的完整测试闭环。
缺陷位置在文件末尾有标注，修复版见 mock_server_fixed.py。
"""
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HOST = "127.0.0.1"
PORT = 18080

# ---------- 测试数据 ----------
USERS = {"test01": "123456", "test02": "abc123"}

INIT_PRODUCTS = {
    1: {"id": 1, "name": "机械键盘", "price": 299.0, "stock": 10},
    2: {"id": 2, "name": "无线鼠标", "price": 99.0, "stock": 5},
    3: {"id": 3, "name": "显示器", "price": 1099.0, "stock": 3},
    4: {"id": 4, "name": "头戴耳机", "price": 250.0, "stock": 20},
}

PRODUCTS = {}
ORDERS = {}
TOKENS = {}
ORDER_LOCK = threading.Lock()


def reset_data():
    """重置库存和订单，保证每条用例从干净状态开始"""
    global PRODUCTS, ORDERS
    PRODUCTS = {k: dict(v) for k, v in INIT_PRODUCTS.items()}
    ORDERS = {}


reset_data()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # 关掉默认访问日志，测试输出更干净

    # ---------- 工具方法 ----------
    def _send(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _auth(self):
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:]
        return None

    # ---------- 路由 ----------
    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/api/products":
            return self._send(200, {"code": 0, "data": list(PRODUCTS.values())})

        if path.startswith("/api/orders/"):
            oid = path.rsplit("/", 1)[-1]
            order = ORDERS.get(oid)
            if not order:
                return self._send(404, {"code": 40401, "msg": "订单不存在"})
            return self._send(200, {"code": 0, "data": order})

        return self._send(404, {"code": 40400, "msg": "接口不存在"})

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/api/login":
            data = self._body()
            username = data.get("username")
            password = data.get("password")
            if USERS.get(username) != password:
                return self._send(401, {"code": 40101, "msg": "用户名或密码错误"})
            token = uuid.uuid4().hex
            TOKENS[token] = username
            return self._send(200, {"code": 0, "data": {"token": token, "username": username}})

        if path == "/api/orders":
            return self._create_order()

        if path == "/api/admin/reset":
            reset_data()
            return self._send(200, {"code": 0, "msg": "已重置"})

        return self._send(404, {"code": 40400, "msg": "接口不存在"})

    def _create_order(self):
        token = self._auth()
        if token not in TOKENS:
            return self._send(401, {"code": 40102, "msg": "未登录或 token 无效"})

        data = self._body()
        product_id = data.get("product_id")
        quantity = data.get("quantity", 0)
        request_id = data.get("request_id")  # 幂等键

        product = PRODUCTS.get(product_id)
        if not product:
            return self._send(404, {"code": 40402, "msg": "商品不存在"})
        if not isinstance(quantity, int) or quantity <= 0:
            return self._send(400, {"code": 40001, "msg": "购买数量必须为正整数"})

        # 【缺陷 1】先查库存、后扣库存，中间有耗时且未加锁
        # 并发下多个请求会同时通过 "库存充足" 校验，导致超卖
        if product["stock"] < quantity:
            return self._send(400, {"code": 40002, "msg": "库存不足"})

        time.sleep(0.05)  # 模拟业务处理耗时，放大并发窗口

        # 【缺陷 2】库存扣减未加锁，且没做二次校验
        product["stock"] -= quantity

        # 【缺陷 3】满 500 减 50，门槛写成 > 500（应为 >= 500）
        amount = round(product["price"] * quantity, 2)
        if amount > 500:
            amount = round(amount - 50, 2)

        # 【缺陷 4】没有幂等校验，同一 request_id 重复提交会生成两笔订单
        order_id = "ORD" + uuid.uuid4().hex[:10].upper()
        order = {
            "order_id": order_id,
            "username": TOKENS[token],
            "product_id": product_id,
            "product_name": product["name"],
            "quantity": quantity,
            "amount": amount,
            "status": "PAID",
            "request_id": request_id,
        }
        ORDERS[order_id] = order
        return self._send(201, {"code": 0, "data": order})


def run_server():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.serve_forever()


if __name__ == "__main__":
    print(f"电商订单服务已启动：http://{HOST}:{PORT}")
    print("按 Ctrl+C 停止")
    run_server()
