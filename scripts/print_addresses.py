"""Print every agent's address (derived from .env seeds) for the README/submission."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.config import BANK_ADDRESS, ORCHESTRATOR_ADDRESS, READER_ADDRESS  # noqa: E402

rows = [(os.getenv("ORCHESTRATOR_NAME", "airlock"), ORCHESTRATOR_ADDRESS),
        (os.getenv("READER_NAME", "airlock_reader"), READER_ADDRESS),
        (os.getenv("BANK_NAME", "airlock_bank"), BANK_ADDRESS)]
for name, addr in rows:
    print(f"{name:22} {addr}")
    print(f"{'':22} https://agentverse.ai/agents/details/{addr}/profile")
