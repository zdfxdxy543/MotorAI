from pathlib import Path
import sys


MOTORAI_ROOT = Path(__file__).resolve().parents[3]
GENERATE_ROOT = MOTORAI_ROOT / 'Generate'
V2_ROOT = GENERATE_ROOT

for import_root in (MOTORAI_ROOT, V2_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))
