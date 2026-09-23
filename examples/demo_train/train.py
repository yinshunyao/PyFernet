"""演示：被加密的训练入口（含 Path(__file__) 相对配置）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from helper import greet

_HERE = Path(__file__).resolve().parent


def main() -> None:
    cfg_path = _HERE / "train_config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    print(greet("PyFernet"))
    print("argv:", sys.argv)
    print("config:", cfg)
    print("__file__:", __file__)
    print("训练逻辑在此启动（YOLO/RTDETR 等）；权重请写到明文磁盘目录。")


if __name__ == "__main__":
    main()
