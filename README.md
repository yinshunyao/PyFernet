# PyFernet (`pyfernet-payload`)

[中文说明](README.zh-CN.md)

Pack a training source directory into a single `.enc` blob; on the client, decrypt and run from an **in-memory VFS**. Only an **empty directory tree** is created on disk (for `Path(__file__)` / `chdir`); `.py` / config **contents are never written**. Removed on exit.

- **Zero third-party runtime deps** (stdlib AES-128-CBC + Fernet-compatible format)
- **PyPI name**: `pyfernet-payload` (`pyfernet` is already taken)
- **CLI / import**: `pyfernet` / `import pyfernet`
- **Relative paths work**: `Path(__file__).parent / "train_config.json"`, `open`, `spec_from_file_location` via VFS hooks

## Install

```bash
pip install pyfernet-payload
```

From a local clone:

```bash
# preferred on older pip / mirrors (no editable hook needed)
python3 -m pip install .

# or editable (dev); if this fails, upgrade pip first:
python3 -m pip install -U pip setuptools wheel
python3 -m pip install -e .
```
## CLI

### Encrypt

```bash
pyfernet encrypt ./my_train -o train_payload.enc -e train.py
# passphrase via prompt; or:
export PYFERNET_PASSWORD='your-secret'
pyfernet encrypt ./my_train -o train_payload.enc -e train.py --password-env PYFERNET_PASSWORD
```

### Run

```bash
pyfernet run train_payload.enc
# forward args to the training entry (after --):
pyfernet run train_payload.enc -- --epochs 50 --batch 8
```

Equivalent:

```bash
python -m pyfernet encrypt ./my_train -o train_payload.enc -e train.py
python -m pyfernet run train_payload.enc
```

## Workflow

1. **Local**: write training code → `pyfernet encrypt` → `train_payload.enc`
2. **SFTP**: upload the ciphertext only (client already has `pip install pyfernet-payload`)
3. **SSH**: `pyfernet run train_payload.enc`, enter passphrase
4. Decrypt into memory → empty dir anchors + VFS hooks → start training; write weights to a normal disk path
5. On exit, remove empty dirs; durable disk still has only ciphertext

If the entry uses sibling dirs (e.g. `train_detect_rtdetrv2/` + `train_detect_cfg/` + `train_detect_yolo/`), **encrypt the parent folder** and set `-e train_detect_rtdetrv2/train_insect.py`.

Inference code, datasets, and weights can stay plaintext on the client.

## IDE variable mode (optional)

With no CLI args, modules use the variables at the bottom of the file:

```bash
python -m pyfernet.encryptor   # no args → SOURCE_DIR / OUTPUT_PATH / ENTRY_POINT
python -m pyfernet.loader      # no args → PAYLOAD_PATH / TRAIN_ARGV
```

With args, they use the CLI, e.g. `python -m pyfernet.encryptor ./src -o out.enc -e train.py`.

## Library API

```python
from pyfernet import encrypt_directory, run_payload

encrypt_directory("examples/demo_train", "dist/train_payload.enc", "train.py", "secret")
run_payload("dist/train_payload.enc", "secret", argv=["train.py", "--epochs", "1"])
```

## Payload format

```text
PYFE1\0  +  16B salt  +  Fernet(token)
```

Fernet plaintext is a zip (sources + `_pyfernet_manifest.json`). The passphrase is stretched with PBKDF2-HMAC-SHA256 (390000 iterations).

## Notes

- Source file **bytes never hit disk**; only empty directories exist briefly (often under `/dev/shm` on Linux)
- Process memory / debuggers can still see plaintext; a leaked passphrase decrypts the blob
- By default only `.py` and a few config suffixes are packed—do not put datasets or weights in the blob
- The client still needs training deps installed (torch, ultralytics, etc.)

## Publish to PyPI

See [docs/PUBLISH.md](docs/PUBLISH.md) ([中文](docs/PUBLISH.zh-CN.md)).

## Layout

```text
PyFernet/
  pyproject.toml
  README.md              # English (PyPI)
  README.zh-CN.md        # Chinese
  src/pyfernet/
    cli.py
    encryptor.py
    loader.py
    fernet_lite.py
  examples/demo_train/
  docs/PUBLISH.md
  docs/PUBLISH.zh-CN.md
```
