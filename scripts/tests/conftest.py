from __future__ import annotations

import sys
from pathlib import Path

# Add scripts/ to import path so we can import upstream
sys.path.insert(0, str(Path(__file__).parent.parent))
