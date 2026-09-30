"""解密 .enc 到内存 VFS 并执行；源码文件不落盘。

磁盘上只建空目录树（供 Path(__file__)/chdir）；内容经 open/Path/import hook 从内存读。
进程结束删除空目录。
"""

from __future__ import annotations

import getpass
import io
import json
import os
import shutil
import sys
import tempfile
import types
import zipfile
from pathlib import Path

from pyfernet.constants import KDF_ITERATIONS, MAGIC, MANIFEST_NAME, SALT_LEN
from pyfernet.fernet_lite import FernetLite, InvalidToken, derive_fernet_key
from pyfernet.vfs import PayloadVFS


def _configure_stdio() -> None:
    """避免非 TTY / nohup / 管道下 stdout 块缓冲导致日志不实时。"""
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
        except Exception:
            try:
                stream.reconfigure(write_through=True)  # type: ignore[attr-defined]
            except Exception:
                pass


def decrypt_payload(enc_path: Path, password: str) -> bytes:
    raw = enc_path.read_bytes()
    if not raw.startswith(MAGIC):
        raise ValueError(f"不是 PyFernet 密文包（magic 不匹配）: {enc_path}")
    salt = raw[len(MAGIC) : len(MAGIC) + SALT_LEN]
    token = raw[len(MAGIC) + SALT_LEN :]
    key = derive_fernet_key(password, salt, KDF_ITERATIONS)
    try:
        return FernetLite(key).decrypt(token)
    except InvalidToken as e:
        raise ValueError("口令错误或密文损坏") from e


def _empty_root() -> Path:
    """仅作路径锚点的空目录（Linux 优先 /dev/shm）。"""
    base: str | None = None
    if sys.platform.startswith("linux"):
        shm = Path("/dev/shm")
        if shm.is_dir():
            base = str(shm)
    return Path(tempfile.mkdtemp(prefix="pyfernet_", dir=base))


def _zip_to_mapping(zip_bytes: bytes) -> tuple[dict[str, bytes], str]:
    mapping: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        if MANIFEST_NAME not in zf.namelist():
            raise ValueError("密文包缺少 manifest")
        manifest = json.loads(zf.read(MANIFEST_NAME).decode("utf-8"))
        entry = str(manifest["entry_point"]).replace("\\", "/")
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if name.endswith("/") or name == MANIFEST_NAME:
                continue
            mapping[name] = zf.read(info)
    return mapping, entry


def list_payload(payload_path: str | Path, password: str) -> tuple[str, list[str]]:
    """解密并返回 (entry_point, 相对路径列表)。"""
    zip_bytes = decrypt_payload(Path(payload_path), password)
    mapping, entry = _zip_to_mapping(zip_bytes)
    return entry, sorted(mapping.keys())


def normalize_entry_rel(entry_point: str) -> str:
    """规范化包内相对入口路径；拒绝绝对路径与 ``..``。"""
    text = str(entry_point or "").strip().replace("\\", "/")
    if not text:
        raise ValueError("入口路径不能为空")
    if text.startswith("/") or Path(text).is_absolute():
        raise ValueError(f"入口须为密文包内相对路径: {entry_point}")
    parts = Path(text).parts
    if ".." in parts:
        raise ValueError(f"入口路径不得包含 '..': {entry_point}")
    rel = Path(*parts).as_posix() if parts else text
    if rel.startswith("./"):
        rel = rel[2:]
    return rel


def resolve_entry_rel(
    mapping: dict[str, bytes],
    default_entry: str,
    entry_point: str | None = None,
) -> str:
    """选择实际执行入口：``entry_point`` 覆盖 manifest 默认值。"""
    if entry_point is None or not str(entry_point).strip():
        chosen = str(default_entry).replace("\\", "/")
    else:
        chosen = normalize_entry_rel(entry_point)
    if chosen not in mapping:
        py_files = [k for k in sorted(mapping) if k.endswith(".py")]
        sample = ", ".join(py_files[:12])
        more = f" …共 {len(py_files)} 个 .py" if len(py_files) > 12 else ""
        raise RuntimeError(
            f"入口不在密文包内: {chosen}\n"
            f"  可用 .py 示例: {sample}{more}"
        )
    return chosen


def run_entry(
    zip_bytes: bytes,
    argv: list[str] | None = None,
    *,
    entry_point: str | None = None,
) -> None:
    _configure_stdio()
    mapping, default_entry = _zip_to_mapping(zip_bytes)
    entry_rel = resolve_entry_rel(mapping, default_entry, entry_point)

    root = _empty_root()
    vfs = PayloadVFS(root, mapping)
    vfs.ensure_dir_tree()
    vfs.install()
    try:
        entry = (root / entry_rel).resolve()
        if argv is not None:
            sys.argv = list(argv)
        else:
            sys.argv = [entry_rel]

        root_s = str(root)
        entry_dir = str(entry.parent)
        for p in (entry_dir, root_s):
            if p in sys.path:
                sys.path.remove(p)
            sys.path.insert(0, p)

        source = vfs.read_bytes(entry)
        main_mod = types.ModuleType("__main__")
        main_mod.__file__ = str(entry)
        parent_pkg = entry_rel.replace("\\", "/").rsplit("/", 1)
        if len(parent_pkg) == 2:
            main_mod.__package__ = parent_pkg[0].replace("/", ".")
        else:
            main_mod.__package__ = ""
        sys.modules["__main__"] = main_mod
        code = compile(source, str(entry), "exec")
        try:
            exec(code, main_mod.__dict__)
        except FileNotFoundError as e:
            missing = str(e)
            hint = _missing_pack_hint(missing, root, mapping)
            if hint:
                raise FileNotFoundError(f"{e}\n{hint}") from e
            raise
    finally:
        vfs.uninstall()
        shutil.rmtree(root, ignore_errors=True)


def _missing_pack_hint(err: str, root: Path, mapping: dict[str, bytes]) -> str:
    """若缺失路径落在 VFS 根下，提示密文包未打包该相对路径。"""
    root_s = str(root.resolve())
    # FileNotFoundError 可能是 "缺少脚本: /path" 或纯路径
    path_str = err
    for prefix in ("缺少脚本: ", "配置不存在: ", "[Errno 2] No such file or directory: "):
        if prefix in err:
            path_str = err.split(prefix, 1)[-1].strip().strip("'\"")
            break
    try:
        rel = Path(path_str).resolve().relative_to(Path(root_s))
    except Exception:
        return ""
    rel_s = rel.as_posix()
    if rel_s in mapping:
        return ""
    top = rel_s.split("/", 1)[0]
    siblings = sorted({p.split("/", 1)[0] for p in mapping})
    return (
        f"pyfernet: 密文包内没有 `{rel_s}`。\n"
        f"  当前包内顶层目录/文件: {siblings}\n"
        f"  请把入口依赖的兄弟目录一起打进加密源目录后重新 encrypt"
        + (f"（例如补上 `{top}/`）。" if top else "。")
    )


def run_payload(
    payload_path: str | Path,
    password: str,
    argv: list[str] | None = None,
    *,
    entry_point: str | None = None,
) -> None:
    """解密并执行密文包（库接口）。

    ``entry_point`` 为包内相对路径时覆盖 manifest 默认入口；``None`` 用加密时的 ``-e``。
    """
    path = Path(payload_path)
    if not path.is_file():
        raise FileNotFoundError(f"找不到密文包: {path}")
    zip_bytes = decrypt_payload(path, password)
    run_entry(zip_bytes, argv=argv, entry_point=entry_point)


def main(
    payload_path: str,
    password: str | None = None,
    argv: list[str] | None = None,
    *,
    entry_point: str | None = None,
) -> None:
    path = Path(payload_path)
    if not path.is_file():
        raise SystemExit(f"找不到密文包: {path}")

    if password is None:
        password = getpass.getpass("解密口令: ")

    run_payload(path, password, argv=argv, entry_point=entry_point)


def _ide_main() -> None:
    PAYLOAD_PATH = "dist/train_payload.enc"
    PASSWORD = None
    ENTRY_POINT = None  # None=manifest 默认；或 "other_entry.py"
    TRAIN_ARGV = ["train.py"]

    main(
        payload_path=PAYLOAD_PATH,
        password=PASSWORD,
        argv=TRAIN_ARGV,
        entry_point=ENTRY_POINT,
    )


if __name__ == "__main__":
    if len(sys.argv) > 1:
        from pyfernet.cli import main as cli_main

        raise SystemExit(cli_main(["run", *sys.argv[1:]]))
    _ide_main()
