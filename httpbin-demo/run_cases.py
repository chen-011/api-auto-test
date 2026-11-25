"""数据驱动小工具：读 CSV 用例 → 自动执行 → 统计通过率。

数据来源与执行逻辑分离：新增用例只改 cases.csv，不用动代码。
运行：python run_cases.py
"""
import csv
import os

# 基于脚本所在目录拼路径，保证在任何目录运行都能找到 CSV
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "cases.csv")


def check_username(username):
    """被测功能：用户名长度必须是 6–12 位。"""
    if len(username) < 6 or len(username) > 12:
        return "长度不合法"
    return "长度合法"


def main():
    pass_count = 0
    total = 0

    # utf-8-sig 自动吃掉文件开头可能存在的 BOM 隐藏字符
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            actual = check_username(row["输入"])
            result = "通过" if actual == row["预期"] else "失败"
            if result == "通过":
                pass_count += 1
            print(f"{row['编号']} 实际:{actual} 预期:{row['预期']} {result}")

    rate = round(pass_count / total * 100, 1)
    print(f"共 {total} 条，通过 {pass_count} 条，通过率 {rate}%")


if __name__ == "__main__":
    main()
