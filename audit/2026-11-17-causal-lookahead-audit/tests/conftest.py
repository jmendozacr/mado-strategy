import os
import sys

AUDIT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.abspath(os.path.join(AUDIT_DIR, "..", ".."))
DETECTOR_DIR = os.path.join(REPO_ROOT, "detector")
SCANNER_DIR = os.path.join(REPO_ROOT, "scanner")
DATA_DIR = os.path.join(REPO_ROOT, "data")

for path in (DETECTOR_DIR, AUDIT_DIR, SCANNER_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)
