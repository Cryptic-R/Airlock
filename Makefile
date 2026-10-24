PY ?= python

.PHONY: setup install test orchestrator reader bank all addresses demo redteam pdf

setup:
	$(PY) -m pip install -r requirements.txt && $(PY) scripts/setup_env.py

install:
	$(PY) -m pip install -r requirements.txt

test:
	$(PY) -m pytest -q tests

orchestrator:
	$(PY) -m agents.orchestrator.agent

reader:
	$(PY) -m agents.reader_agent.agent

bank:
	$(PY) -m agents.bank_agent.agent

all:
	$(PY) run_all.py

addresses:
	$(PY) scripts/print_addresses.py

demo:
	$(PY) scripts/demo_pipeline.py

redteam:
	$(PY) -m pytest -q tests/test_redteam.py -s

pdf:
	$(PY) scripts/make_submission_pdf.py
