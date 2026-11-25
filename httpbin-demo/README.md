# 接口自动化测试框架（Python + requests + pytest）

一个从零搭建的接口自动化测试项目，用于系统练习接口测试与自动化测试的核心流程。
被测对象为公开测试接口 [httpbin.org](https://httpbin.org)（专门供测试学习使用，无需鉴权）。

## 技术栈

- **Python 3.13**
- **requests** —— 发送 HTTP 请求
- **pytest** —— 测试框架（用例发现、断言、参数化、报告）
- **CSV** —— 数据驱动，存放测试用例

## 项目结构

```
.
├── config.py          # 配置集中管理：接口地址、超时时间
├── test_api.py        # 接口自动化测试主文件（GET/POST/断言/参数化）
├── run_cases.py       # 数据驱动小工具（读 CSV → 执行 → 统计通过率）
├── cases.csv          # 测试用例数据（与代码分离）
├── requirements.txt   # 依赖清单
└── .gitignore         # 忽略缓存、虚拟环境等文件
```

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行接口自动化测试
python -m pytest test_api.py -v

# 3. 运行数据驱动小工具
python run_cases.py
```

## 运行结果（真实输出）

接口自动化测试 —— 7 条用例全部通过：

```
test_api.py::test_get_status PASSED                          [ 14%]
test_api.py::test_get_params PASSED                          [ 28%]
test_api.py::test_post_json PASSED                           [ 42%]
test_api.py::test_username_param[zhangsan] PASSED            [ 57%]
test_api.py::test_username_param[lisi] PASSED                [ 71%]
test_api.py::test_username_param[wangwu] PASSED              [ 85%]
test_api.py::test_username_param[] PASSED                    [100%]
============================= 7 passed in 17.61s ==============================
```

数据驱动小工具 —— 5 条用例，通过率 100%：

```
TC01 实际:长度不合法 预期:长度不合法 通过
TC02 实际:长度合法 预期:长度合法 通过
TC03 实际:长度合法 预期:长度合法 通过
TC04 实际:长度不合法 预期:长度不合法 通过
TC05 实际:长度不合法 预期:长度不合法 通过
共 5 条，通过 5 条，通过率 100.0%
```

## 项目亮点

### 1. 配置与逻辑分离
`config.py` 集中管理接口地址和超时时间。换测试环境只改一处，不用翻遍每个测试函数。

### 2. 数据驱动（用例与代码分离）
测试用例存放在 `cases.csv`，执行逻辑在 `run_cases.py`。新增用例只改 CSV，不改代码——这是自动化测试的核心思想。

### 3. 参数化测试
用 `@pytest.mark.parametrize` 让一段测试逻辑覆盖多组数据，`test_username_param` 一份代码跑了 4 组数据（含空值场景），每条独立报告、互不影响。

### 4. 覆盖三种传参方式
- `params=` —— 参数拼在 URL 上（GET）
- `json=` —— JSON 格式放请求体，自动带 `Content-Type: application/json`（POST）
- 通过断言校验服务端是否正确收到参数。

### 5. 踩坑与解决记录
- **BOM 编码坑**：CSV 文件开头的隐藏字符 `\ufeff` 导致 `KeyError`。解决：读取时用 `encoding="utf-8-sig"` 自动吃掉 BOM。
- **相对路径坑**：换个目录运行就 `FileNotFoundError`。解决：用 `__file__` 拼出基于脚本位置的绝对路径，任何目录都能跑。

## 说明

本项目用于学习和面试演示，接口为公开测试接口，不涉及真实业务数据。
