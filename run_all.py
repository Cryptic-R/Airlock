"""Start all three Airlock agents as separate processes (Ctrl+C stops them all)."""

import signal
import subprocess
import sys
import time

MODULES = ["agents.reader_agent.agent", "agents.bank_agent.agent", "agents.orchestrator.agent"]


def main() -> None:
    procs = []
    for m in MODULES:
        procs.append(subprocess.Popen([sys.executable, "-m", m]))
        time.sleep(2)
    print("\nAll agents started. Open each agent's Agent Inspector link above and connect its mailbox.\n")
    try:
        while all(p.poll() is None for p in procs):
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            if p.poll() is None:
                p.send_signal(signal.SIGINT)
        for p in procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    main()
