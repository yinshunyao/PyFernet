from pathlib import Path
import os, sys
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
os.chdir(_HERE)
from src.core import register
from src import optim
print("ok", register(), optim.x)
