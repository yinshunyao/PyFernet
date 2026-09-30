"""命令行入口：pyfernet encrypt | run"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from pyfernet import __version__
from pyfernet.encryptor import main as encrypt_main
from pyfernet.loader import list_payload, main as run_main


DEFAULT_PASSWORD_ENV = "PYFERNET_PASSWORD"


def _password_from_args(password: str | None, password_env: str | None) -> str | None:
    """解析口令：-p > --password-env > 环境变量 PYFERNET_PASSWORD > None(交互)。"""
    if password is not None:
        return password
    env_name = password_env or DEFAULT_PASSWORD_ENV
    # 显式传了 --password-env，或默认名在环境里有值时，走环境变量
    if password_env is not None or env_name in os.environ:
        value = os.environ.get(env_name)
        if not value:
            raise SystemExit(
                f"环境变量未设置或为空: {env_name}\n"
                f"  --password-env 后面是「变量名」不是口令本身。\n"
                f"  正确示例:\n"
                f"    export {DEFAULT_PASSWORD_ENV}='你的口令'\n"
                f"    nohup pyfernet run train.enc --password-env {DEFAULT_PASSWORD_ENV} > d.log 2>&1 &\n"
                f"  或（会进进程列表，仅临时用）:\n"
                f"    nohup pyfernet run train.enc -p '你的口令' > d.log 2>&1 &"
            )
        return value
    return None


def _split_script_args(argv: list[str]) -> tuple[list[str], list[str]]:
    """将 `run ... -- script_args` 拆开，避免 REMAINDER 吞掉 -p/--password-env。"""
    if argv and argv[0] == "run" and "--" in argv:
        idx = argv.index("--")
        return argv[:idx], argv[idx + 1 :]
    return argv, []


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pyfernet",
        description="将源码目录加密为单个 .enc，并在内存中解密运行（磁盘无明文源码）。",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_enc = sub.add_parser("encrypt", help="打包并加密源码目录")
    p_enc.add_argument("source_dir", type=Path, help="要加密的源码目录")
    p_enc.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("train_payload.enc"),
        help="输出密文路径（默认: train_payload.enc）",
    )
    p_enc.add_argument(
        "-e",
        "--entry",
        default="train.py",
        help="相对源目录的入口脚本（默认: train.py）",
    )
    p_enc.add_argument(
        "-p",
        "--password",
        default=None,
        help="口令（不推荐写在命令行；默认交互输入）。也可用 --password-env",
    )
    p_enc.add_argument(
        "--password-env",
        default=None,
        metavar="VAR",
        help="从环境变量读口令（填变量名，如 PYFERNET_PASSWORD；不是口令本身）",
    )

    p_run = sub.add_parser(
        "run",
        help="解密密文包并在内存中执行",
        epilog=(
            "覆盖入口: pyfernet run a.enc -e export_core.py\n"
            "传给脚本的参数写在 -- 之后: pyfernet run a.enc -- --epochs 10"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_run.add_argument("payload", type=Path, help="密文包路径（.enc）")
    p_run.add_argument(
        "-e",
        "--entry",
        default=None,
        metavar="REL",
        help="覆盖运行入口（密文包内相对路径）；默认用加密时的 -e",
    )
    p_run.add_argument(
        "-p",
        "--password",
        default=None,
        help="口令（不推荐写在命令行；默认交互输入）。也可用 --password-env",
    )
    p_run.add_argument(
        "--password-env",
        default=None,
        metavar="VAR",
        help="从环境变量读口令（填变量名，如 PYFERNET_PASSWORD；不是口令本身）",
    )

    p_list = sub.add_parser("list", help="列出密文包内文件（需口令）")
    p_list.add_argument("payload", type=Path, help="密文包路径（.enc）")
    p_list.add_argument("-p", "--password", default=None, help="口令（默认交互输入）")
    p_list.add_argument(
        "--password-env",
        default=None,
        metavar="VAR",
        help="从环境变量读口令（填变量名；不是口令本身）",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    cli_argv, script_args = _split_script_args(raw)

    parser = build_parser()
    args = parser.parse_args(cli_argv)

    if args.command == "encrypt":
        password = _password_from_args(args.password, args.password_env)
        encrypt_main(
            source_dir=str(args.source_dir),
            output_path=str(args.output),
            entry_point=args.entry,
            password=password,
        )
        return 0

    if args.command == "run":
        password = _password_from_args(args.password, args.password_env)
        entry_override = str(args.entry).strip() if args.entry else None
        argv0 = entry_override or Path(args.payload).name
        train_argv = [argv0, *script_args]
        run_main(
            payload_path=str(args.payload),
            password=password,
            argv=train_argv,
            entry_point=entry_override,
        )
        return 0

    if args.command == "list":
        password = _password_from_args(args.password, args.password_env)
        if password is None:
            import getpass

            password = getpass.getpass("解密口令: ")
        entry, files = list_payload(args.payload, password)
        print(f"entry: {entry}")
        print(f"files: {len(files)}")
        for name in files:
            print(name)
        return 0

    parser.error(f"未知命令: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
