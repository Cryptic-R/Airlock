"""Run the Airlock engine over the demo inbox in the terminal (no agents, no key needed).

Usage: python scripts/demo_pipeline.py
Shows what gets paid autonomously and what is held for you.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import Airlock, CredulousPlanner  # noqa: E402
from engine.seed import INBOX, build_mandates, build_store  # noqa: E402

MARK = {"ALLOW": "handled ", "ESCALATE": "needs you", "BLOCK": "refused  "}


def main() -> None:
    lock = Airlock(build_store(), build_mandates(), CredulousPlanner())
    for msg in INBOX:
        res = lock.process(msg)
        print(f"\n{msg['id']}  {res.subject}  (from {msg['from']})")
        for o in res.outcomes:
            print(f"   {MARK[o.decision]}  {o.action}")
            if o.receipt:
                print(f"               -> {o.receipt}")
            for r in o.reasons:
                print(f"               . {r}")
    print("\nWaiting for you:")
    for item in lock.escalations.open_items():
        print(f"  - {item.summary}")
        for r in item.reasons:
            print(f"      {r.text}")
    new = lock.store.payments[lock.store.seeded:]
    print(f"\n{len(new)} bill(s) paid autonomously, {sum(p.amount for p in new):,.2f} total; "
          f"{len(lock.escalations.open_items())} decision(s) held; "
          f"audit intact = {lock.audit.verify()}")


if __name__ == "__main__":
    main()
