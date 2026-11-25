"""
电商订单服务 —— 修复版
与 mock_server.py 的唯一区别是修掉了 3 个缺陷，用于演示"缺陷修复后回归全部通过"。

修复点：
  缺陷1+2 超卖 → 扣减放进锁内，并在锁内二次校验库存
  缺陷3 满减门槛 → > 500 改为 >= 500
  缺陷4 幂等 → 用 request_id 去重，重复请求直接返回已有订单
"""
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HOST = "127.0.0.1"
PORT = 18080

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
ORDER_LOCK = threading.Lock()      # 保护库存扣减
REQUEST_CACHE = {}                 # 幂等键 -> 订单号


def reset_data():
    global PRODUCTS, ORDERS, REQUEST_CACHE
    PRODUCTS = {k: dict(v) for k, v in INIT_PRODUCTS.items()}
    ORDERS = {}
    REQUEST_CACHE = {}


reset_data()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

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
        return auth[7:] if auth.startswith("Bearer ") else None

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
            if USERS.get(data.get("username")) != data.get("password"):
                return self._send(401, {"code": 40101, "msg": "用户名或密码错误"})
            token = uuid.uuid4().hex
            TOKENS[token] = data["username"]
            return self._send(200, {"code": 0, "data": {"token": token, "username": data["username"]}})
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
        request_id = data.get("request_id")

        product = PRODUCTS.get(product_id)
        if not product:
            return self._send(404, {"code": 40402, "msg": "商品不存在"})
        if not isinstance(quantity, int) or quantity <= 0:
            return self._send(400, {"code": 40001, "msg": "购买数量必须为正整数"})

        # 修复缺陷 1 和 2：查库存 + 扣库存 + 幂等判断，全部放进同一把锁
        with ORDER_LOCK:
            if request_id and request_id in REQUEST_CACHE:
                return self._send(200, {"code": 0, "data": ORDERS[REQUEST_CACHE[request_id]]})

            time.sleep(0.01)

            if product["stock"] < quantity:
                return self._send(400, {"code": 40002, "msg": "库存不足"})

            product["stock"] -= quantity

            # 修复缺陷 3：满 500 减 50，门槛用 >=
            amount = round(product["price"] * quantity, 2)
            if amount >= 500:
                amount = round(amount - 50, 2)

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
            if request_id:
                REQUEST_CACHE[request_id] = order_id

        return self._send(201, {"code": 0, "data": order})


def run_server():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.serve_forever()


if __name__ == "__main__":
    print(f"电商订单服务（修复版）已启动：http://{HOST}:{PORT}")
    run_server()
