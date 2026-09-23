"""将指定目录的训练代码打包并 Fernet 加密为单个 .enc 文件。"""

from __future__ import annotations

import getpass
import io
import json
import os
import zipfile
from pathlib import Path

from pyfernet.constants import (
    ALLOW_NAMES,
    ALLOW_SUFFIXES,
    KDF_ITERATIONS,
    MAGIC,
    MANIFEST_NAME,
    SALT_LEN,
    SKIP_DIRS,
    SKIP_SUFFIXES,
)
from pyfernet.fernet_lite import FernetLite, derive_fernet_key


def should_include(path: Path, root: Path) -> bool:
    rel_parts = path.relative_to(root).parts
    if any(p in SKIP_DIRS for p in rel_parts):
        return False
    if path.suffix.lower() in SKIP_SUFFIXES:
        return False
    return path.suffix.lower() in ALLOW_SUFFIXES or path.name in ALLOW_NAMES


def build_zip_bytes(source_dir: Path, entry_point: str) -> bytes:
    source_dir = source_dir.resolve()
    if not source_dir.is_dir():
        raise FileNotFoundError(f"源目录不存在: {source_dir}")

    entry = Path(entry_point)
    entry_rel = str(entry).replace("\\", "/")
    entry_abs = (source_dir / entry).resolve()
    try:
        entry_abs.relative_to(source_dir)
    except ValueError as e:
        raise FileNotFoundError(f"入口文件不在源目录内: {entry_point}") from e
    if not entry_abs.is_file():
        raise FileNotFoundError(f"入口文件不存在: {entry_point}")

    buf = io.BytesIO()
    files: list[str] = []
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(source_dir.rglob("*")):
            if not path.is_file():
                continue
            if not should_include(path, source_dir):
                continue
            arcname = path.relative_to(source_dir).as_posix()
            zf.write(path, arcname)
            files.append(arcname)

        if entry_rel not in files:
            raise RuntimeError(f"入口 {entry_rel} 未被打包（后缀可能被过滤）")

        manifest = {
            "version": 1,
            "entry_point": entry_rel,
            "files": files,
        }
        zf.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))

    return buf.getvalue()


def encrypt_bytes(plain: bytes, password: str) -> bytes:
    salt = os.urandom(SALT_LEN)
    key = derive_fernet_key(password, salt, KDF_ITERATIONS)
    token = FernetLite(key).encrypt(plain)
    return MAGIC + salt + token


def encrypt_directory(
    source_dir: str | Path,
    output_path: str | Path,
    entry_point: str,
    password: str,
) -> Path:
    zip_bytes = build_zip_bytes(Path(source_dir), entry_point)
    enc = encrypt_bytes(zip_bytes, password)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(enc)
    return out


def prompt_password_confirm() -> str:
    password = getpass.getpass("加密口令: ")
    confirm = getpass.getpass("再输入一次: ")
    if password != confirm:
        raise SystemExit("两次口令不一致")
    if not password:
        raise SystemExit("口令不能为空")
    return password


def main(
    source_dir: str,
    output_path: str,
    entry_point: str,
    password: str | None = None,
) -> None:
    if password is None:
        password = prompt_password_confirm()

    out = encrypt_directory(source_dir, output_path, entry_point, password)
    size = out.stat().st_size
    print(f"已生成: {out.resolve()} ({size} bytes)")
    print(f"入口: {entry_point}")
    print("请妥善保存口令；口令不会写入密文文件。")


def _ide_main() -> None:
    # —— IDE 调试：改变量后直接运行本模块 ——
    SOURCE_DIR = "examples/demo_train"
    OUTPUT_PATH = "dist/train_payload.enc"
    ENTRY_POINT = "train.py"
    PASSWORD = None

    main(
        source_dir=SOURCE_DIR,
        output_path=OUTPUT_PATH,
        entry_point=ENTRY_POINT,
        password=PASSWORD,
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        from pyfernet.cli import main as cli_main

        raise SystemExit(cli_main(["encrypt", *sys.argv[1:]]))
    _ide_main()
