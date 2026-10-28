"""Builds Chanakya-Documentation.pdf: a cover page, a contents page and every project document, in reading order.

    backend\\venv\\Scripts\\python tools\\build_docs_pdf.py

Needs the `markdown` package (pip install markdown) and Google Chrome or Microsoft Edge (used headless to print the PDF). Nothing is uploaded anywhere.
CLAUDE.md (instructions for the AI coding assistant) is not project documentation and is left out.
"""
from __future__ import annotations

import html
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Chanakya-Documentation.pdf"

# (title shown in the contents, file, part)
DOCS = [
    ("README: overview, features, models, languages, tech stack, API", "README.md", "Overview"),
    ("Product requirements (PRD)", "prd.md", "Product"),
    ("Problem statement", "problem_statement.md", "Product"),
    ("Pitch", "pitch.md", "Product"),
    ("Plan", "PLAN.md", "Product"),
    ("To do", "todo.md", "Product"),
    ("Progress log and git history", "progress.md", "Engineering log"),
    ("Issues and fixes log", "issues.md", "Engineering log"),
    ("Orchestration", "docs/orchestration.md", "Design notes"),
    ("Long videos in parts", "docs/plan-long-videos.md", "Design notes"),
    ("Presentation mode", "docs/presentation-mode.md", "Design notes"),
    ("Voice assistant", "docs/voice-assistant.md", "Design notes"),
    ("RAG and OCR: design", "docs/superpowers/specs/2026-10-27-rag-ocr-design.md", "Design notes"),
    ("RAG and OCR: implementation plan", "docs/superpowers/plans/2026-10-27-rag-ocr.md", "Design notes"),
    ("Earlier detailed notes and per-version changelog", "docs/README-notes.md", "Design notes"),
    ("Blender 3D lessons (Dhiraj)", "blender 3d/README.md", "Teammate modules"),
    ("Learnverse metaverse (Niharika)", "metaverse/README.md", "Teammate modules"),
    ("Niharika: voice assistant and metaverse notes", "Niharika/README.md", "Teammate modules"),
    ("Niharika 01: current state", "Niharika/01-current-state.md", "Teammate modules"),
    ("Niharika 02: architecture", "Niharika/02-architecture.md", "Teammate modules"),
    ("Niharika 03: speech to text", "Niharika/03-speech-to-text.md", "Teammate modules"),
    ("Niharika 04: talk-back text to speech", "Niharika/04-talkback-tts.md", "Teammate modules"),
    ("Niharika 05: topic knowledge", "Niharika/05-topic-knowledge.md", "Teammate modules"),
    ("Niharika 06: live demo", "Niharika/06-ltx-live-demo.md", "Teammate modules"),
    ("Niharika 07: roadmap, testing and risks", "Niharika/07-roadmap-testing-risks.md", "Teammate modules"),
    ("Dhiraj: RAG and OCR build notes", "Dhiraj/README.md", "Teammate modules"),
]

TEAM = [("Team name", "The Last Commit"), ("Members", "Aryan Dubey, Priyadarshini Prasad, Niharika K P, Dhiraj Shetty"),
        ("College", "RV University, Bengaluru"), ("Course", "B.Tech (Hons)"), ("Branch", "Computer Science Engineering"), ("Year of study", "2nd year")]

CSS = """
@page { size: A4; margin: 18mm 15mm 18mm 15mm; @bottom-center { content: "Chanakya, The Last Commit  |  page " counter(page); font: 9px sans-serif; color: #666; } }
* { box-sizing: border-box; }
body { font-family: "Segoe UI", "Noto Sans", Arial, sans-serif; font-size: 10.5pt; line-height: 1.5; color: #1b1b1f; }
h1 { font-size: 22pt; margin: 0 0 8pt; padding-bottom: 5pt; border-bottom: 2px solid #1b1b1f; }
h2 { font-size: 15pt; margin: 18pt 0 6pt; padding-bottom: 3pt; border-bottom: 1px solid #c9c9d1; break-after: avoid; }
h3 { font-size: 12pt; margin: 14pt 0 4pt; break-after: avoid; }
h4, h5 { font-size: 10.5pt; margin: 10pt 0 3pt; break-after: avoid; }
p, li { orphans: 3; widows: 3; }
code { font-family: "Cascadia Mono", Consolas, monospace; font-size: 9pt; background: #f1f1f5; padding: 0 3px; border-radius: 3px; }
pre { background: #f6f6f9; border: 1px solid #dcdce4; border-radius: 5px; padding: 7pt 9pt; font-size: 8.4pt; line-height: 1.35; white-space: pre-wrap; word-break: break-word; break-inside: avoid; }
pre code { background: none; padding: 0; font-size: inherit; }
table { border-collapse: collapse; width: 100%; margin: 7pt 0; font-size: 9pt; break-inside: auto; }
tr { break-inside: avoid; }
th, td { border: 1px solid #c9c9d1; padding: 3.5pt 6pt; vertical-align: top; text-align: left; word-break: break-word; }
th { background: #ececf2; }
blockquote { margin: 7pt 0; padding: 3pt 10pt; border-left: 3px solid #b8b8c4; color: #444; background: #fafafc; }
a { color: #1a4fb4; text-decoration: none; }
hr { border: 0; border-top: 1px solid #d5d5dd; margin: 12pt 0; }
.doc { break-before: page; }
.part { break-before: page; text-align: center; padding-top: 80mm; }
.part h1 { border: 0; font-size: 28pt; }
.part p { color: #666; }
.cover { text-align: center; padding-top: 38mm; }
.cover .name { font-size: 48pt; font-weight: 800; letter-spacing: 1px; margin: 0; }
.cover .sub { font-size: 14pt; color: #444; margin: 6pt 0 26mm; }
.cover table { width: 118mm; margin: 0 auto; font-size: 11.5pt; }
.cover td:first-child { background: #ececf2; font-weight: 700; width: 38mm; }
.cover .foot { margin-top: 24mm; color: #666; font-size: 10pt; }
.toc td, .toc th { border: 0; border-bottom: 1px dotted #c9c9d1; }
.toc .part-row td { font-weight: 700; background: #ececf2; border: 0; }
"""


def render(md_text: str) -> str:
    md = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists", "attr_list"], output_format="html5")
    return md.convert(md_text)


def demote(md_text: str) -> str:
    """Each document keeps its own '#' title as the top heading of its section (the contents lists them); nothing to change but stray YAML front matter."""
    return re.sub(r"\A---\n.*?\n---\n", "", md_text, flags=re.S)


def chrome() -> str:
    for p in (r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
        if Path(p).exists():
            return p
    found = shutil.which("chrome") or shutil.which("google-chrome") or shutil.which("msedge")
    if not found:
        sys.exit("Google Chrome or Microsoft Edge is needed to print the PDF.")
    return found


def main() -> None:
    parts: list[str] = []
    cover_rows = "".join(f"<tr><td>{html.escape(k)}</td><td>{html.escape(v)}</td></tr>" for k, v in TEAM)
    parts.append(f'<section class="cover"><p class="name">Chanakya</p><p class="sub">An offline AI teacher: narrated, animated lessons in nine languages</p>'
                 f"<table>{cover_rows}</table>"
                 f'<p class="foot">Complete project documentation · v0.16.0<br>https://github.com/signingoff-dubey/UNLOX-TEACHER</p></section>')
    included = [(t, f, p) for t, f, p in DOCS if (ROOT / f).exists()]
    missing = [f for _, f, _ in DOCS if not (ROOT / f).exists()]
    rows, last = [], None
    for t, f, part in included:
        if part != last:
            rows.append(f'<tr class="part-row"><td colspan="2">{html.escape(part)}</td></tr>')
            last = part
        rows.append(f"<tr><td>{html.escape(t)}</td><td><code>{html.escape(f)}</code></td></tr>")
    parts.append(f'<section class="doc toc"><h1>Contents</h1><table>{"".join(rows)}</table>'
                 "<p>Each document starts on a new page. The first part is the README, which is the best single overview; the rest is the product definition, "
                 "the engineering log (every version and every bug with its fix), design notes and the modules written by each teammate.</p></section>")
    last = None
    for t, f, part in included:
        if part != last:
            parts.append(f'<section class="part"><h1>{html.escape(part)}</h1><p>{html.escape(t)} and the documents that follow</p></section>')
            last = part
        text = demote((ROOT / f).read_text(encoding="utf-8", errors="replace"))
        parts.append(f'<section class="doc"><p style="color:#777;font-size:8.5pt;margin:0">{html.escape(f)}</p>{render(text)}</section>')
    page = f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Chanakya: project documentation</title><style>{CSS}</style></head><body>{"".join(parts)}</body></html>'
    tmp = Path(tempfile.mkdtemp(prefix="chanakya-docs-"))
    src = tmp / "docs.html"
    src.write_text(page, encoding="utf-8")
    profile = tmp / "profile"
    cmd = [chrome(), "--headless=new", "--disable-gpu", f"--user-data-dir={profile}", "--no-pdf-header-footer", "--no-sandbox",
           f"--print-to-pdf={OUT}", src.as_uri()]
    subprocess.run(cmd, check=True, timeout=300, capture_output=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"{OUT} ({OUT.stat().st_size / 1e6:.1f} MB), {len(included)} documents" + (f"; not found: {missing}" if missing else ""))


if __name__ == "__main__":
    main()
