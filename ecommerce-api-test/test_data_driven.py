"""
数据驱动测试 —— 用例写在 cases.csv 里，代码只负责读和跑

为什么这么做（面试考点）：
  数据和代码分离。以后加用例只改 CSV，不用动一行 Python 代码。
  这就是 pytest 参数化 + 数据驱动的落地形式，也是企业里最常见的做法。
"""
import csv
import os

import pytest
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "cases.csv")


def load_cases():
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


CASES = load_cases()
IDS = [c["case_id"] for c in CASES]


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_order_from_csv(base_url, auth_headers, case):
    payload = {
        "product_id": int(case["product_id"]),
        "quantity": int(case["quantity"]),
    }
    r = requests.post(f"{base_url}/api/orders", headers=auth_headers, json=payload, timeout=5)

    assert r.status_code == int(case["expect_status"]), \
        f"{case['case_id']} {case['remark']}：期望 {case['expect_status']}，实际 {r.status_code}"

    if case["expect_amount"]:
        assert r.json()["data"]["amount"] == float(case["expect_amount"]), \
            f"{case['case_id']} {case['remark']}：金额不符"
