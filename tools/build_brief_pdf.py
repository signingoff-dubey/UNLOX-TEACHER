"""Builds Chanakya-Brief.pdf: a short (at most 5 pages) written summary of the project, in paragraphs, with the models used.

    backend\\venv\\Scripts\\python tools\\build_brief_pdf.py

Chrome or Edge (headless) prints the page. The long version is tools/build_docs_pdf.py (Chanakya-Documentation.pdf).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Chanakya-Brief.pdf"

CSS = """
@page { size: A4; margin: 9mm 10mm 11mm 10mm; @bottom-center { content: "Chanakya  |  The Last Commit  |  " counter(page); font: 8px sans-serif; color: #777; } }
* { box-sizing: border-box; }
body { font-family: "Segoe UI", "Noto Sans", Arial, sans-serif; font-size: 10.3pt; line-height: 1.4; color: #1b1b1f; margin: 0; text-align: justify; hyphens: auto; }
.head { border-bottom: 2px solid #1b1b1f; padding-bottom: 4pt; margin-bottom: 5pt; }
.head h1 { font-size: 27pt; margin: 0; letter-spacing: .5px; display: inline; }
.head .tag { font-size: 11pt; color: #444; margin-left: 8pt; }
.meta { font-size: 9.2pt; color: #333; line-height: 1.45; margin: 3pt 0 0; text-align: left; }
.meta b { color: #000; }
.cols { column-count: 2; column-gap: 7mm; column-fill: balance; }
h2 { font-size: 12pt; margin: 7pt 0 2pt; padding-bottom: 1pt; border-bottom: 1px solid #c9c9d1; break-after: avoid; text-align: left; }
h2:first-child { margin-top: 0; }
p { margin: 0 0 4pt; orphans: 3; widows: 3; }
code { font-family: "Cascadia Mono", Consolas, monospace; font-size: 9pt; background: #f1f1f5; padding: 0 2px; border-radius: 2px; }
.cmd { font-family: "Cascadia Mono", Consolas, monospace; font-size: 8.4pt; background: #f6f6f9; border: 1px solid #dcdce4; border-radius: 3px; padding: 3pt 5pt; margin: 2pt 0 4pt; text-align: left; white-space: pre-wrap; break-inside: avoid; }
em { color: #333; }
"""

BODY = """
<div class="head">
  <h1>Chanakya</h1><span class="tag">An offline AI teacher: narrated, animated lessons in nine languages</span>
  <p class="meta"><b>Team name:</b> The Last Commit &nbsp;·&nbsp; <b>Members:</b> Aryan Dubey, Priyadarshini Prasad, Niharika K P, Dhiraj Shetty<br>
  <b>College:</b> RV University, Bengaluru &nbsp;·&nbsp; <b>Course:</b> B.Tech (Hons) &nbsp;·&nbsp; <b>Branch:</b> Computer Science Engineering &nbsp;·&nbsp; <b>Year:</b> 2nd year<br>
  <b>Repo:</b> github.com/signingoff-dubey/UNLOX-TEACHER &nbsp;·&nbsp; <b>Version:</b> v0.16.0 &nbsp;·&nbsp; <b>Built for:</b> the Unlox hackathon</p>
</div>

<div class="cols">

<h2>The problem and our answer</h2>
<p>Learners in India need short visual explanations in their own language, but the good ones are online-only, English-first, or built on paid cloud AI. Students on ordinary laptops, often with poor internet, are left out. Chanakya is a local-first teacher: you type a topic (or attach a photo or a PDF) and, with Wi-Fi off, it writes a lesson, narrates it in your language, animates it, and lets you watch it in the browser or export an MP4 with captions. No outside AI service is ever called, and the same product also runs entirely on an Android phone.</p>

<h2>How a lesson is made</h2>
<p>The one rule that shapes the design is that the AI only returns <em>data</em>: a JSON lesson, checked against a schema, that picks one of eleven scene templates and fills in its text. Our own code draws, times and renders every frame, and nothing the model writes is ever executed. The request is first cleaned (&ldquo;teach me about dsa in java&rdquo; becomes &ldquo;DSA in Java&rdquo;), then the system remembers which related videos the learner already owns, retrieves facts from an offline knowledge base (Simple English Wikipedia, our own reference notes and any PDF the learner attached), and asks the local language model for a plan. The plan is repaired and sent back with feedback if it repeats itself, has thin narration or shows a technical topic only as text; repeated scenes are removed, a visual director swaps weak scene choices, a writer pass lengthens short narration, and a fact checker verifies the statements. The English plan is then translated, each sentence is spoken with a delivery that fits it, and every scene lasts exactly as long as its audio, so voice, captions and visuals never drift.</p>

<h2>What it can do</h2>
<p>Lessons run from 30 seconds to 4 minutes; a course is one to three videos, and &ldquo;Auto&rdquo; lets the AI count the concepts in a topic. The eleven scene types are title, bullets, flow, cycle, compare, diagram, quiz, summary, <strong>graph</strong> (lines, parabolas, circles, ellipses, sine waves and more, with points, tangents and chords), <strong>code</strong> (syntax-coloured, with a highlight that follows the narration) and <strong>network</strong> (boxes and arrows for trees, linked structures and pipelines). Four modes fit the learner: Explanation, Study, Homework (teaches the method and writes the answers into a separate file) and Revise (re-teaches what the learner keeps getting wrong). A photo of a page or a board is read by a local vision model, and PDFs up to 2 GB and 1,000 pages are read as Markdown, with OCR for scans and a description of every picture inside, so a lesson can teach a single chapter with page citations. Around the video there is a tutor chat (text or voice) that can build &ldquo;one more video&rdquo; on request, study tools (flashcards, quiz, mind map, glossary, FAQ, timeline), spaced-repetition review, teach-it-back grading, rewards, worksheets and question papers, MP4, captions and audio export, an offline bundle for a USB stick, and Learnverse, a walkable 3D world the local model builds from any topic.</p>

<h2>Flash and Pro</h2>
<p><strong>Flash</strong> shows scenes within seconds and keeps writing while you watch: a short outline, then parts of about 40 seconds written one after another, each told what the earlier parts already taught. <strong>Pro</strong> shows nothing until the whole video is planned: it first outlines every scene, writes the first minute in one call, and patches each further minute on with the whole outline and all earlier text in view, then gives the fact checker twice the time. Both use the same model. On &ldquo;teach me what avl trees are&rdquo; (two minutes), Flash finished in 133 seconds with the first scenes watchable after 18, while Pro took 167 seconds and covered balance factor, single and double rotations, insertion, deletion and uses in a more coherent order.</p>

<h2>Models used</h2>
<p>Everything runs locally, and models served from remote servers are refused. The <strong>language model</strong> for planning, directing, writing, fact checking, the tutor and the study tools is <strong>Qwen2.5-7B-Instruct</strong> (Q4_K_M, Apache-2.0) served by Ollama, fully resident on the 8 GB GPU at about 43 tokens per second with a 6,144-token context. Photos and pictures inside PDFs are read by <strong>LLaVA 7B</strong>. Retrieval uses <strong>nomic-embed-text</strong> for the knowledge base, <strong>multilingual-e5-small</strong> for PDF passages and <strong>bge-reranker-v2-m3</strong> to re-rank them. Translation uses <strong>NLLB-200 distilled 600M</strong> by default, with <strong>AI4Bharat IndicTrans2</strong> (200M, gated) as an option and a back-translation check on every sentence. Narration uses <strong>Piper</strong> voices (English, Hindi, Telugu, Malayalam, Marathi, Bengali), <strong>AI4Bharat Indic-TTS</strong> int8 ONNX voices on the CPU (Tamil, Kannada, Gujarati and others) and <strong>Indic Parler-TTS</strong> on the GPU as a tone-aware fallback. Speech to text is <strong>faster-whisper</strong>; scanned pages go through <strong>Tesseract</strong> and then <strong>Unlimited-OCR</strong> when the GPU is idle. A larger model, <code>qwen3.5:9b</code>, was benchmarked and rejected: only 72% of it fits on the card and it ran at 17 tokens per second. On the phone the equivalents are <strong>Gemma 4 E2B</strong> (LiteRT-LM), Piper through <strong>sherpa-onnx</strong>, <strong>Whisper</strong> with <strong>Vosk</strong>, and <strong>ML Kit</strong> for translation and OCR.</p>

<h2>Languages and voices</h2>
<p>Nine languages are supported: English, Hindi, Telugu, Marathi, Bengali, Malayalam, Tamil, Kannada and Gujarati. The lesson is sized for the slowest voice chosen (from about 2.7 words per second in English down to 1.6 in Telugu and Malayalam), a missing voice falls back to the next engine and finally to correctly timed silence, and the Noto fonts bundled with the player draw every script, conjuncts included. If a translation fails the script or meaning check, English is kept instead of showing a bad translation.</p>

<h2>Quality and fact checking</h2>
<p>Because a 7-billion-parameter model writes fluently but sometimes wrongly, the plan is judged before it is spoken. A <strong>fact checker</strong> works without any outside service: it calculates arithmetic and linear equations, checks a count against its list and a few lists every child learns (the rainbow, the planets in order, the continents), and compares each statement with passages retrieved for it. A verdict only counts if the judge quotes words that really appear in the source and a second, focused question agrees; a correction must pass the same check, otherwise the statement is removed without leaving a scene too thin. A <strong>memory</strong> module tells the planner what the learner already has so videos build on each other instead of repeating hooks and examples, and technical topics are shown with real code (in the language the learner names) or a drawn tree, with at most one everyday comparison, instead of a forced analogy. The report of what was checked, confirmed, corrected or removed is saved with each lesson.</p>

<h2>Robustness</h2>
<p>Jobs resume after a crash, a GPU out-of-memory falls back to the CPU and retries, a memory gate waits when the laptop is short of RAM or VRAM, calls to Ollama are retried when it is busy, and a readiness check (<code>/api/ready</code>) names anything missing and the command that fixes it. The backend has 345 automated tests, and live lessons on a dozen topics were generated in both modes to find and fix the defects the tests could not.</p>

<h2>Tech stack</h2>
<p><strong>Backend:</strong> Python 3.12, FastAPI, Pydantic, SQLite, PyTorch (CUDA 12.8), Transformers, ONNX Runtime, sentence-transformers, FAISS, PyMuPDF and pymupdf4llm. <strong>Web:</strong> React 18, TypeScript, Vite, Remotion for the player and the headless MP4 renderer (Chrome and ffmpeg), three.js for Learnverse, Mermaid for mind maps. <strong>Android:</strong> Kotlin, Jetpack Compose, Room, WorkManager, Media3. <strong>3D lessons:</strong> a headless Blender pipeline. The user interface follows the team&rsquo;s Figma design.</p>

<h2>Performance and hardware</h2>
<p>Built and measured on an RTX 5060 laptop with 8 GB of VRAM and 15 GB of RAM. The first scene of a short lesson appears about 1.2 seconds after planning starts (6 to 18 seconds from the click in Flash), a two-minute video takes two to three minutes to build, a thousand-page scanned PDF is searchable in under three minutes, and the language model, translator and voices share the card by taking turns. The Android app was tested on a OnePlus 13R.</p>

<h2>Known limits</h2>
<p>The 7B model still makes occasional factual slips; the checker removes what it can prove wrong and reports the rest as unconfirmed. Code is displayed rather than run (only Python is syntax-checked). The Android app does not yet have Flash and Pro, the fact checker or memory. Wikipedia text is CC BY-SA 4.0 and every lesson lists the articles it used; model and voice licences are listed in the README.</p>

<h2>Run it</h2>
<div class="cmd">git clone https://github.com/signingoff-dubey/UNLOX-TEACHER.git
.\\setup.ps1 -Gpu     # once, online
.\\start.ps1          # http://127.0.0.1:8000</div>
<p>Needs Ollama (<code>qwen2.5:7b-instruct-q4_K_M</code>, <code>nomic-embed-text</code>, <code>llava:7b</code>). The full documentation, with every version and every bug and its fix, is in <code>Chanakya-Documentation.pdf</code>.</p>

</div>
"""


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
    page = f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Chanakya: brief</title><style>{CSS}</style></head><body>{BODY}</body></html>'
    tmp = Path(tempfile.mkdtemp(prefix="chanakya-brief-"))
    src = tmp / "brief.html"
    src.write_text(page, encoding="utf-8")
    subprocess.run([chrome(), "--headless=new", "--disable-gpu", f"--user-data-dir={tmp / 'profile'}", "--no-pdf-header-footer", "--no-sandbox",
                    f"--print-to-pdf={OUT}", src.as_uri()], check=True, timeout=300, capture_output=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"{OUT} ({OUT.stat().st_size / 1e3:.0f} KB)")


if __name__ == "__main__":
    main()
