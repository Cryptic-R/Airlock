"""Create .env from .env.example with fresh random seed phrases (keeps an existing .env)."""

import secrets
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
env, example = root / ".env", root / ".env.example"
if env.exists():
    print(".env already exists; not overwriting. Delete it first if you want new agent identities.")
    sys.exit(0)
lines = []
for line in example.read_text().splitlines():
    key = line.split("=", 1)[0]
    if key.endswith("_SEED_PHRASE"):
        line = f"{key}={secrets.token_urlsafe(32)}"
    lines.append(line)
env.write_text("\n".join(lines) + "\n")
print("Created .env with random seeds. Now paste your ASI1_API_KEY into it.")
