# Setup guide — Airlock: steps only you can do (about 20 minutes)

The code is ready. These steps need your accounts, your machine and your keys.

## 1. Accounts and keys
| # | Step | Where | Notes |
|---|---|---|---|
| 1 | Sign up / log in to **ASI:One** | <https://asi1.ai> | Same login is used for Agentverse |
| 2 | Create an **ASI:One API key** | <https://asi1.ai/dashboard/api-keys> | Paste into `.env` as `ASI1_API_KEY=`. Never commit it |
| 3 | Log in to **Agentverse** | <https://agentverse.ai> | Needed to connect mailboxes and edit agent profiles |
| 4 | Open the **Fetch-A-Thon 3.0 dashboard** once and check you're registered | <https://asi1.ai/festival/fetchathon3/dashboard> | The Project Submission Agent and AI Mentor live here |
| 5 | Create an **empty public GitHub repo** (no README/license; we have them) | <https://github.com/new> | Name it `airlock` (or anything) |
| 6 | (For the Pro/payment demo) get **testnet FET** into your ASI:One wallet | Copy your wallet address (starts with `fetch1`), open <https://explore-dorado.fetch.ai/> → **Get Funds** → paste it (gives 1 TESTFET). Docs: <https://network.fetch.ai/docs/guides/ledger/faucet> | Optional, but payments are bonus points. Set `ENABLE_PAYMENTS=false` to skip |

## 2. Machine setup
Python **3.10-3.13** (3.12 recommended). Then, inside the `starter/` folder:

**Windows (PowerShell)**
```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1
notepad .env          # paste ASI1_API_KEY, rename the agents
```

**macOS / Linux**
```bash
bash setup.sh
nano .env
```
The setup script creates `.venv`, installs dependencies, writes `.env` with **random seed phrases**
(these are your agents' identities; keep the same `.env` from now on or the addresses change), runs the
offline tests and prints the agent addresses.

## 3. First live run (proves your network, key and Agentverse work)
```bash
python scripts/demo_pipeline.py   # real LLM + API, no agents
python run_all.py                                                     # starts all 3 agents
```
For **each** agent, open the **Agent Inspector** link printed in its log → **Connect** → **Mailbox**.
Wait for `Successfully registered as mailbox agent in Agentverse`.

Then on the orchestrator inspector → **Agent Profile** → **Chat with Agent** → say `hi` in ASI:One.
You should get a form card. Complete the flow once.

## 4. Push to GitHub
```bash
git init
git add .
git status          # .env must NOT be listed
git commit -m "Initial agent"
git branch -M main
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```
Check `.env` is **not** in the repo (it's in `.gitignore`).

## 5. Keep agents alive until results (28 Oct)
Judges test after the event. Leave `python run_all.py` running on a machine that stays on, e.g. a cloud
VM in `tmux`/`nohup`, or your laptop with sleep disabled. Mailbox agents only answer while running.

## If something breaks
| Symptom | Fix |
|---|---|
| Agent never replies in ASI:One | Mailbox not connected: open inspector → Connect → Mailbox; agent process must be running |
| `ASI1_API_KEY not set` in logs | Key missing in `.env`; the agent still works with rule-based fallback |
| Footer says "local fallback" | A helper agent isn't running or its mailbox isn't connected; result still works |
| Address changed | You regenerated `.env`; restore the old seeds |
| Card shows as plain text | Card payload failed validation; run `python -m pytest` to see which card |
