# PyFernet (`pyfernet-payload`)

[English](README.md)

把训练源码目录打成单个 `.enc` 密文；客户机解密后进入**内存 VFS** 运行。磁盘上只建**空目录树**（供 `Path(__file__)` / `chdir`），**.py/配置内容不落盘**；退出后删空目录。

- **零第三方依赖**（纯标准库 AES-128-CBC + Fernet 兼容格式）
- **PyPI 包名**：`pyfernet-payload`（`pyfernet` 已被占用）
- **命令 / 导入**：`pyfernet` / `import pyfernet`
- **相对路径可用**：`Path(__file__).parent / "train_config.json"`、`open`、`spec_from_file_location` 走 VFS hook

## 安装

```bash
pip install pyfernet-payload
```

本地源码安装：

```bash
# 推荐（旧 pip / 国内镜像也可用，不依赖 editable hook）
python3 -m pip install .

# 或可编辑安装；若报 build_editable 缺失，先升级 pip：
python3 -m pip install -U pip setuptools wheel
python3 -m pip install -e .
```
## 命令行

### 加密

```bash
pyfernet encrypt ./my_train -o train_payload.enc -e train.py
# 口令交互输入；或：
export PYFERNET_PASSWORD='your-secret'
pyfernet encrypt ./my_train -o train_payload.enc -e train.py --password-env PYFERNET_PASSWORD
```

### 运行

```bash
pyfernet run train_payload.enc
# 传参给训练脚本（-- 之后原样转发）：
pyfernet run train_payload.enc -- --epochs 50 --batch 8
```

等价：

```bash
python -m pyfernet encrypt ./my_train -o train_payload.enc -e train.py
python -m pyfernet run train_payload.enc
```

## 工作流

1. **本地**：写训练代码 → `pyfernet encrypt` → 得到 `train_payload.enc`
2. **SFTP**：只上传密文包（客户机已 `pip install pyfernet-payload`）
3. **SSH**：`pyfernet run train_payload.enc`，输入口令
4. 解密进内存 → 空目录锚点 + VFS hook → 启动训练；权重写到普通磁盘目录
5. 退出后删除空目录；持久磁盘仍只有密文

若入口依赖兄弟目录（如 `train_detect_rtdetrv2/` + `train_detect_cfg/` + `train_detect_yolo/`），请**加密它们的父目录**，并设 `-e train_detect_rtdetrv2/train_insect.py`。

推理代码、数据集、权重继续明文放客户机即可。

## IDE 变量模式（可选）

无命令行参数时，可直接运行模块底部变量入口：

```bash
python -m pyfernet.encryptor   # 无额外参数 → 使用模块内 SOURCE_DIR 等
python -m pyfernet.loader      # 无额外参数 → 使用模块内 PAYLOAD_PATH 等
```

有参数时自动走 CLI，例如 `python -m pyfernet.encryptor ./src -o out.enc -e train.py`。

## 库接口

```python
from pyfernet import encrypt_directory, run_payload

encrypt_directory("examples/demo_train", "dist/train_payload.enc", "train.py", "secret")
run_payload("dist/train_payload.enc", "secret", argv=["train.py", "--epochs", "1"])
```

## 密文格式

```text
PYFE1\0  +  16B salt  +  Fernet(token)
```

Fernet 明文为 zip（源码 + `_pyfernet_manifest.json`）。口令经 PBKDF2-HMAC-SHA256（390000 次）派生密钥。

## 注意

- **源码字节不落盘**；磁盘上仅短暂存在空目录（Linux 上常在 `/dev/shm`）
- 运行时内存 / 调试器仍可能看到明文；口令泄露则密文可解
- 默认只打包 `.py` 与少量配置后缀；不要把数据集、权重打进包
- 客户机需已安装训练依赖（torch、ultralytics 等）

## 发布到 PyPI

见 [docs/PUBLISH.zh-CN.md](docs/PUBLISH.zh-CN.md)（[English](docs/PUBLISH.md)）。

## 目录

```text
PyFernet/
  pyproject.toml
  README.md              # 英文（PyPI）
  README.zh-CN.md        # 中文
  src/pyfernet/
    cli.py
    encryptor.py
    loader.py
    fernet_lite.py
  examples/demo_train/
  docs/PUBLISH.md
  docs/PUBLISH.zh-CN.md
```
