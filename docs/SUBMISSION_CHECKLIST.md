# Fetch-A-Thon 3.0 submission checklist — Airlock (Everyday Agents track)

> **Event day is Saturday 24 Oct 2026.** Building runs 10:30 to 16:30 IST, **"Final Building & Submission" is 16:30 IST**, closing at 17:50, end 18:00. Aim to submit by **16:00** so you have time to fix a broken link. Results: Wed 28 Oct, 12:15 IST.
>
> Only projects that meet **all six mandatory requirements** are eligible for prizes, and **submission through the ASI:One dashboard is mandatory** for online and offline participants.

---

## A. Mandatory requirements (all six, or no prize)

| # | Requirement (from the challenge) | How the starter meets it | Verify before submitting |
|---|---|---|---|
| 1 | Register at least one agent on Agentverse | All agents run with `mailbox=True`, `publish_agent_details=True` | Each agent's log shows "registered as mailbox agent"; each has a profile page on agentverse.ai |
| 2 | Implement the Agent Chat Protocol (ACP) | `chat_protocol_spec` (AgentChatProtocol 0.3.0) with `publish_manifest=True` in `agents/orchestrator/chat.py` | Agentverse profile → Protocols tab lists *AgentChatProtocol* |
| 3 | Discoverable and directly usable through ASI:One | Profile name/handle/README with keywords (`docs/agentverse_readmes/`), "Chat with Agent" opens it in ASI:One | Open ASI:One in a **fresh browser / incognito**, find Airlock, "Run my inbox" works |
| 4 | Meaningful tool execution or multi-agent orchestration | Orchestrator runs the planner→gate→actor; Reader agent supplies untrusted input, Bank agent settles approved actions; Payment Protocol settles in FET | Terminal logs show ReadRequest/ExecRequest hops; summary + review cards appear |
| 5 | Complete primary workflow entirely within an ASI:One conversation | Run inbox / paste email → summary card → one review (approve/decline) card per held decision → Payment Protocol on approve; no custom frontend | Do the whole flow once in ASI:One and **share that chat** |
| 6 | Public GitHub repository with instructions to run or test | README "Run it", `.env.example`, setup scripts, `pytest` (engine + red team + chat flow), `make demo` | Open the repo URL **logged out**; README renders; no `.env` or seeds committed |

## B. Deliverables (what you submit to the Project Submission Agent)

| # | Deliverable | Where it comes from | Done |
|---|---|---|---|
| 1 | **Public ASI:One Shared Chat URL** showing the complete workflow | In ASI:One, after the full demo chat → Share → copy public link | ☐ |
| 2 | **Agentverse Agent Profile URL(s)** for **each** submitted agent | `python scripts/print_addresses.py` prints address + profile URL for each | ☐ ☐ ☐ |
| 3 | **Public GitHub repository** | `https://github.com/<you>/<repo>` (public) | ☐ |
| 4 | **Short demo video** (hackpack: **3-5 minutes**) | Follow `docs/DEMO_SCRIPT.md`; upload to YouTube (Unlisted is fine) or Drive (anyone with link can view) | ☐ |
| 5 | **Brief description**: problem, target users, outcome | `docs/PROJECT_DESCRIPTION.md` (ready to paste; Everyday Agents track) | ☐ |

### Hackpack "What to submit" extras (judges check these in the repo)
- ☐ README lists **each agent's name and address** (fill the table in README after `python scripts/print_addresses.py`)
- ☐ README has the **`innovationlab`** and **`hackathon`** badges (already in README and the Agentverse READMEs):
  `![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)` `![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)`
- ☐ README lists any extra resources needed to run it (ASI:One API key, Agentverse account; already in README)

## C. How to submit (official steps)
1. Open the **Fetch-A-Thon 3.0 Dashboard**: <https://asi1.ai/festival/fetchathon3/dashboard>
2. Select the **Project Submission Agent** from the agents on the dashboard.
3. Follow its instructions and give it **all five deliverables**: GitHub repo, ASI:One Shared Chat URL, Agentverse profile URL(s), demo video link, project description.
4. **Verify** the submission: every link opens in a logged-out/incognito window, and the agent confirms your submission.
5. Screenshot the confirmation for your records.

(Stuck while building? The dashboard also has an **AI Mentor** agent.)

## D. Bonus points the starter already covers
- ✅ Multi-agent collaboration (3 agents, typed agent-to-agent protocols)
- ✅ Payment Protocol settles approved bills in FET (credible: you pay the bill you approved)
- ✅ ASI Interactive Cards (summary, mandates, and an approve/decline review card per decision)
- ✅ Reliability: retries, timeouts, local fallback, user-facing error cards, never-silent handler
- ✅ Realistic household inbox incl. a live injection attempt; audit chain is tamper-evident
- ✅ Can keep running after the hackathon (engine needs no external API; low cost)

## E. Things that commonly sink submissions
- ❌ **Agents stopped after you submit.** Judges test after the event (results 28 Oct). Keep all agents running until then: a cloud VM (`nohup python run_all.py &` or a `tmux` session), or at least your laptop on and awake. Mailbox agents only reply while their process runs.
- ❌ Shared chat link is private, or shows only "hi" and not the full flow.
- ❌ Repo is private, or `.env` with seeds/API key was committed (rotate the key if so).
- ❌ Video longer than 5 min, or a link that needs permission to view.
- ❌ Only the orchestrator's profile URL submitted; submit **one per agent**.
- ❌ Agent name/README too vague to be found in ASI:One search.

---

## F. What to put in the PDF

The official challenge **does not ask for a PDF**: the five deliverables above go to the Project
Submission Agent as links/text. If your college, team lead, or the submission agent asks for a
document, use this structure (`python scripts/make_submission_pdf.py` builds it from
`docs/submission.json`). Each section is mapped to what judges score.

| # | PDF section | Content | Maps to |
|---|---|---|---|
| 1 | **Title page** | Project name, one-liner, team name and members, hackathon + track ("ASI:One Agent Challenge: From Intent to Action"), date | Presentation |
| 2 | **Submission links** (clickable) | ASI:One shared chat URL · Agentverse profile URL per agent · GitHub repo · demo video | All 5 deliverables |
| 3 | **Problem statement** | The problem, who suffers, why current tools fail | Deliverable 5; Real-world impact (20%) |
| 4 | **Target users** | Primary and secondary users | Deliverable 5 |
| 5 | **Solution & outcome** | What the agent *does* (actions, not chat); example output | Deliverable 5; Innovation (20%) |
| 6 | **Mandatory requirements compliance** | Table A above, one row per requirement with evidence | Eligibility |
| 7 | **Architecture** | Agent diagram, agent names + addresses, protocols, data sources | Functionality (25%); Fetch.ai tech (20%) |
| 8 | **Fetch.ai technology used** | Agentverse, Chat Protocol, ASI:One LLM (where in the flow), Payment Protocol, Interactive Cards | Fetch.ai tech (20%) |
| 9 | **User workflow in ASI:One** | Step-by-step with 3-5 screenshots (prompt, confirm card, plan card, payment, calendar) | UX (15%); Requirement 5 |
| 10 | **Reliability & error handling** | Failure-handling table | Bonus |
| 11 | **Monetisation** | Free/Pro, price, B2B model | Bonus; Fetch.ai tech |
| 12 | **Impact & metrics** | Water saved, inputs saved, users reachable | Real-world impact |
| 13 | **How to run / test** | 5-line quick start + link to README | Requirement 6 |
| 14 | **Limitations & roadmap** | Honest limits, next steps | Continuity bonus |
| 15 | **Team & contact** | Names, roles, emails/GitHub | Admin |

Keep it to **5-8 pages**, screenshots over prose, and make sure every link in it is clickable and public.
