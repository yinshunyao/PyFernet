"""演示：同一密文包内可被 run --entry 覆盖启动的另一入口。"""

from __future__ import annotations

import sys

from helper import greet


def main() -> None:
    print(greet("other_entry"))
    print("other_entry argv:", sys.argv)
    print("__file__:", __file__)


if __name__ == "__main__":
    main()
