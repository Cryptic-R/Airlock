"""Build docs/Submission.pdf from docs/submission.json.

Fill in the JSON, drop screenshots into docs/screenshots/, then:
    python scripts/make_submission_pdf.py
"""

import json
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
D = json.loads((ROOT / "docs" / "submission.json").read_text(encoding="utf-8"))
OUT = ROOT / "docs" / "Submission.pdf"

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], textColor=colors.HexColor("#1e3a8a"))
H2 = ParagraphStyle("H2", parent=ss["Heading2"], textColor=colors.HexColor("#1d4ed8"), spaceBefore=10)
BODY = ParagraphStyle("B", parent=ss["BodyText"], fontSize=10, leading=14)
SMALL = ParagraphStyle("S", parent=BODY, fontSize=8.5, leading=11)
HEAD_BG = colors.HexColor("#dbeafe")


def p(text, style=BODY):
    return Paragraph(escape(str(text)), style)


def link(url):
    return Paragraph(f'<link href={quoteattr(url)} color="blue"><u>{escape(url)}</u></link>', SMALL)


def table(rows, widths):
    rows = [[c if not isinstance(c, str) else p(c, SMALL) for c in r] for r in rows]
    t = Table(rows, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG)]))
    return t


def bullets(items):
    return [p(f"• {i}") for i in items]


def build():
    L = D["links"]
    s = [Spacer(1, 3 * cm), p(D["project_name"], H1), p(D["one_liner"]), Spacer(1, 12),
         p("Fetch-A-Thon 3.0 · ASI:One Agent Challenge: From Intent to Action"), p(f"Team: {D['team_name']}")]
    s += bullets(D["members"]) + [PageBreak()]

    s.append(p("1. Submission links", H2))
    rows = [["Deliverable", "Link"], ["ASI:One shared chat (complete workflow)", link(L["asi1_shared_chat_url"])],
            ["Public GitHub repository", link(L["github_repo_url"])], ["Demo video", link(L["demo_video_url"])]]
    rows += [[f"Agentverse profile: {a['name']}", link(a["profile_url"])] for a in D["agents"]]
    s.append(table(rows, [6 * cm, 11 * cm]))

    s += [p("2. Problem", H2), p(D["problem"]), p("3. Target users", H2)] + bullets(D["target_users"])
    s += [p("4. Solution and outcome", H2)] + bullets(D["outcome"])

    s.append(p("5. Mandatory requirements compliance", H2))
    s.append(table([
        ["Requirement", "Evidence"],
        ["Agent registered on Agentverse", f"{len(D['agents'])} mailbox agents; profile links in section 1"],
        ["Agent Chat Protocol (ACP)", "AgentChatProtocol 0.3.0 with published manifest (agents/orchestrator/chat.py)"],
        ["Discoverable & usable via ASI:One", "Agentverse profile + README keywords; 'Chat with Agent'; shared chat link"],
        ["Meaningful tool execution / orchestration", D["architecture"]],
        ["Workflow fully inside ASI:One", "Request -> cards -> result -> action, no custom frontend"],
        ["Public GitHub repo with run/test steps", "README, .env.example, setup scripts, offline tests"],
    ], [6 * cm, 11 * cm]))

    s += [p("6. Architecture", H2), p(D["architecture"]), Spacer(1, 6)]
    s.append(table([["Agent", "Role", "Address", "Protocols"]] +
                   [[a["name"], a["role"], a["address"], a["protocols"]] for a in D["agents"]],
                   [3.5 * cm, 4.5 * cm, 5 * cm, 4 * cm]))
    s += [p("7. Fetch.ai technology used", H2)] + bullets(D["fetch_tech"])

    s += [PageBreak(), p("8. User workflow in ASI:One", H2)]
    for shot in D["screenshots"]:
        f = ROOT / shot["file"]
        if f.exists():
            img = Image(str(f))
            ratio = img.imageHeight / img.imageWidth
            img.drawWidth, img.drawHeight = 14 * cm, min(14 * cm * ratio, 16 * cm)
            s += [img, p(shot["caption"], SMALL), Spacer(1, 8)]
        else:
            s.append(p(f"[Screenshot placeholder: {shot['caption']}; save as {shot['file']}]", SMALL))

    s += [p("9. Reliability and error handling", H2), table([["Failure", "Behaviour"]] + D["reliability"], [6 * cm, 11 * cm])]
    s += [p("10. Monetisation", H2)] + bullets(D["monetisation"])
    s += [p("11. Impact", H2), p(D["impact"])]
    s += [p("12. How to run / test", H2), p(D["run_steps"], SMALL)]
    s += [p("13. Limitations and roadmap", H2)] + bullets(D["roadmap"])

    SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                      bottomMargin=1.8 * cm, title=f"{D['project_name']} - Fetch-A-Thon 3.0").build(s)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    build()
