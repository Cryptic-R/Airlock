"""Print non-secret local readiness and optionally check the ASI:One planner."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import config, asi1
from engine import Airlock, LLMPlanner
from engine.seed import build_mandates, build_store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', help='Send one synthetic bill to ASI:One')
    args = parser.parse_args()
    print(json.dumps({
        'python': sys.version.split()[0],
        'asi_key_configured': bool(config.ASI1_API_KEY),
        'payments_enabled': config.ENABLE_PAYMENTS,
        'orchestrator': config.ORCHESTRATOR_ADDRESS,
        'reader': config.READER_ADDRESS,
        'bank': config.BANK_ADDRESS,
    }, indent=2))
    if args.live:
        if not config.ASI1_API_KEY:
            raise SystemExit('Set ASI1_API_KEY in .env first. Do not share it in chat.')
        planner = LLMPlanner(lambda messages: asi1.chat(messages, retries=0, timeout=45))
        lock = Airlock(build_store(), build_mandates(), planner)
        result = lock.process({'id': 'live-check', 'subject': 'Acme Power invoice',
                               'body': 'Amount due $84.20.'})
        live = result.narrative == 'Planned by ASI:One LLM.'
        print(json.dumps({'live_planner_used': live, 'decision': result.headline,
                          'actions': [o.action for o in result.outcomes]}, indent=2))
        if not live or result.headline != 'ALLOW' or len(lock.store.payments) != lock.store.seeded + 1:
            raise SystemExit('Live planner verification failed; inspect the logged status.')


if __name__ == '__main__':
    main()
