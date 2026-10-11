"""Run the full weekly pipeline from your machine (uses .env).

    python scripts/run_digest.py
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from pulse.pipeline import run_digest  # noqa: E402

if __name__ == "__main__":
    result = asyncio.run(run_digest("cli"))
    print(json.dumps(result, indent=2, default=str))
