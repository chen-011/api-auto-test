"""
pytest 公共配置：启动被测服务 + 提供登录态 fixture

为什么这么写（面试会问）：
1. 被测服务用线程启动，测试跑完自动关闭，不需要手动开两个窗口
2. token 做成 session 级 fixture，登录一次全用例复用，避免每条用例都登录
3. 每条用例前调用 /api/admin/reset 重置数据，保证用例之间互不影响
   —— 这叫"用例独立性"，是自动化测试能稳定跑的前提
"""
import importlib
import os
import threading
import time

import pytest
import requests

# 通过环境变量切换被测版本：默认测「有缺陷版」，设为 fixed 则测「修复版」
MOCK_MODULE = "mock_server_fixed" if os.environ.get("MOCK_VERSION") == "fixed" else "mock_server"
_mock = importlib.import_module(MOCK_MODULE)
PORT, HOST, run_server = _mock.PORT, _mock.HOST, _mock.run_server

BASE_URL = f"http://{HOST}:{PORT}"


def _wait_ready(timeout=10):
    """等服务起来，避免测试抢跑导致连接被拒"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            requests.get(f"{BASE_URL}/api/products", timeout=1)
            return True
        except requests.exceptions.ConnectionError:
            time.sleep(0.1)
    raise RuntimeError("被测服务启动超时")


@pytest.fixture(scope="session", autouse=True)
def server():
    """整个测试会话只启动一次服务"""
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    _wait_ready()
    yield
    # daemon 线程随进程退出，无需显式关闭


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def token(base_url):
    """登录一次，拿到 token 给所有用例复用"""
    r = requests.post(f"{base_url}/api/login",
                      json={"username": "test01", "password": "123456"}, timeout=5)
    assert r.status_code == 200, f"登录失败：{r.text}"
    return r.json()["data"]["token"]


@pytest.fixture(autouse=True)
def clean_data(base_url):
    """每条用例执行前重置库存和订单，保证用例互不影响"""
    requests.post(f"{base_url}/api/admin/reset", timeout=5)
    yield


@pytest.fixture
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}
