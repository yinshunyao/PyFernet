# PyPI 发布说明（pyfernet-payload）

[English](PUBLISH.md)

> PyPI 上 `pyfernet` 名称已被占用，本项目发布名为 **`pyfernet-payload`**。  
> 安装后命令与导入仍为：`pyfernet` / `import pyfernet`。

## 发布前检查

1. 确认 `pyproject.toml` 中 `version`（当前与 `pyfernet.__version__` 保持一致）。
2. 本地可编辑安装并自测：

```bash
cd PyFernet
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -U pip setuptools wheel
python3 -m pip install -e .   # 或: python3 -m pip install .
pip install build twine

pyfernet --version
pyfernet encrypt examples/demo_train -o dist/train_payload.enc -e train.py --password-env PYFERNET_PASSWORD
PYFERNET_PASSWORD=... pyfernet run dist/train_payload.enc --password-env PYFERNET_PASSWORD
```

3. 确认 README 示例与 CLI 一致。

## 构建

```bash
# 清理旧产物
rm -rf build/ dist/*.whl dist/*.tar.gz src/*.egg-info *.egg-info

python -m build
```

产物应在 `dist/`：

- `pyfernet_payload-0.2.5-py3-none-any.whl`
- `pyfernet_payload-0.2.5.tar.gz`

## 上传 TestPyPI（推荐先测）

1. 在 https://test.pypi.org/ 注册账号，创建 API token。
2. 配置 `~/.pypirc`（勿提交到 git）：

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-你的正式Token

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-你的TestToken
```

3. 上传并试装：

```bash
twine upload --repository testpypi dist/*

pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ pyfernet-payload
```

## 上传正式 PyPI

```bash
twine upload dist/*
# 或
twine upload --repository pypi dist/*
```

安装：

```bash
pip install pyfernet-payload
```

## 版本 bump

发新版时同步改两处：

1. `src/pyfernet/__init__.py` → `__version__`（`setup.py` 也会读这里）
2. `pyproject.toml` → `[project].version`

建议用语义化版本：`0.1.0` → `0.1.1`（修复）/ `0.2.0`（功能）。

## 客户机用法（发布后）

只需安装包 + 上传密文，无需再拷贝 `loader.py`：

```bash
pip install pyfernet-payload
# 上传 train_payload.enc 后
pyfernet run train_payload.enc
```

## 配置清单

| 项 | 位置 | 说明 |
|---|---|---|
| 发布名 | `pyproject.toml` `name` | `pyfernet-payload` |
| 导入名 | `src/pyfernet/` | `import pyfernet` |
| CLI | `[project.scripts]` | `pyfernet = pyfernet.cli:main` |
| 版本 | `pyproject.toml` + `__init__.py` | 保持一致 |
| 许可证 | `LICENSE` + `license` | MIT |
| Python | `requires-python` | `>=3.10` |
| 依赖 | `dependencies` | 空（纯标准库） |
| 仓库 URL | `[project.urls]` | 按实际 GitHub 地址改 |
| 作者 | `authors` | 按需修改 |
| 文档 | `README.md` / `README.zh-CN.md` | 英文给 PyPI，中文镜像 |
