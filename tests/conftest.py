import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Unit tests run without any installed DEM unless a test asks for one, so the
# smooth-sphere expectations do not depend on which data files are present.
# Tests that use the real LOLA grids load them explicitly (tests/test_realdata.py).
REAL_DEM_DIR = os.environ.get("SLIPDAY_DEM_DIR") or os.path.join(os.path.dirname(__file__), "..", "data", "dem")
os.environ["SLIPDAY_REAL_DEM_DIR"] = os.path.abspath(REAL_DEM_DIR)
_empty = tempfile.mkdtemp(prefix="slipday_nodem_")
os.environ["SLIPDAY_DEM_DIR"] = _empty
os.environ["SLIPDAY_HORIZON_CACHE"] = tempfile.mkdtemp(prefix="slipday_hcache_")
os.environ.pop("SLIPDAY_SYNTHETIC_DEM", None)
