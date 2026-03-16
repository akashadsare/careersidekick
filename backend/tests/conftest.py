import sys
from pathlib import Path
import os

# Ensure app module is in path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Use SQLite for tests
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'