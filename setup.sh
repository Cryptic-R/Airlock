#!/usr/bin/env bash
# One-time setup on macOS/Linux:  bash setup.sh
set -e
PY=${PY:-python3}
$PY -m venv .venv
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt
python scripts/setup_env.py || true
python -m pytest -q
python scripts/print_addresses.py
echo ""
echo "Next: put ASI1_API_KEY in .env, then:  source .venv/bin/activate && python run_all.py"
