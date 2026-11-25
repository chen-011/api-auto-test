"""接口自动化测试主文件（pytest）

覆盖：GET / POST 请求、三种传参方式、响应断言、参数化。
运行：python -m pytest test_api.py -v
"""
import requests
import pytest
from config import BASE_URL, TIMEOUT


def test_get_status():
    """基础：GET 请求返回 200。"""
    response = requests.get(f"{BASE_URL}/get", timeout=TIMEOUT)
    assert response.status_code == 200


def test_get_params():
    """GET：参数是否正确传到服务器（params 放 URL）。"""
    response = requests.get(
        f"{BASE_URL}/get", params={"username": "zhangsan"}, timeout=TIMEOUT
    )
    data = response.json()
    assert data["args"]["username"] == "zhangsan"


def test_post_json():
    """POST：json 传参 + Content-Type 校验。"""
    response = requests.post(
        f"{BASE_URL}/post", json={"username": "lisi"}, timeout=TIMEOUT
    )
    data = response.json()
    assert data["json"]["username"] == "lisi"
    assert data["headers"]["Content-Type"] == "application/json"


@pytest.mark.parametrize("username", ["zhangsan", "lisi", "wangwu", ""])
def test_username_param(username):
    """参数化：一份逻辑覆盖多组数据，空值场景也覆盖。"""
    response = requests.get(
        f"{BASE_URL}/get", params={"username": username}, timeout=TIMEOUT
    )
    data = response.json()
    assert data["args"]["username"] == username
