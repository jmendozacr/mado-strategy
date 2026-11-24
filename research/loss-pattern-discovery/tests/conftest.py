import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent
DETECTOR_ROOT = REPO_ROOT / "detector"

for _path in (LAB_ROOT, DETECTOR_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
