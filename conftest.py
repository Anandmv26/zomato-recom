"""
conftest.py (project root)
--------------------------
Ensures the project root is always on sys.path when pytest runs,
so `phase1_data_pipeline`, `phase2_llm_engine`, etc. are importable
as top-level packages regardless of where pytest is invoked from.
"""
import sys
from pathlib import Path

# Add the project root to sys.path if not already there
ROOT = Path(__file__).parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
