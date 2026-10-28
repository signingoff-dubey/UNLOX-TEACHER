"""Builds Chanakya-Brief.pdf: a short (at most 5 pages) written summary of the project, in paragraphs, with the models used.

    backend\\venv\\Scripts\\python tools\\build_brief_pdf.py [body size in pt]

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
BASE_PT = 10.0        # body size; the text is sized to fill two pages

CSS = """
@page { size: A4; margin: 9mm 10mm 11mm 10mm; @bottom-center { content: "Chanakya  |  The Last Commit  |  " counter(page); font: 8px sans-serif; color: #777; } }
* { box-sizing: border-box; }
body { font-family: "Segoe UI", "Noto Sans", Arial, sans-serif; font-size: %(pt)spt; line-height: 1.42; color: #1b1b1f; margin: 0; text-align: justify; hyphens: auto; }
.head { border-bottom: 2px solid #1b1b1f; padding-bottom: 4pt; margin-bottom: 5pt; }
.head h1 { font-size: 27pt; margin: 0; letter-spacing: .5px; display: inline; }
.head .tag { font-size: 11pt; color: #444; margin-left: 8pt; }
.meta { font-size: 9.2pt; color: #333; line-height: 1.45; margin: 3pt 0 0; text-align: left; }
.meta b { color: #000; }
.cols { column-count: 2; column-gap: 7mm; column-fill: balance; }
h2 { font-size: 12pt; margin: 8pt 0 2pt; padding-bottom: 1pt; border-bottom: 1px solid #c9c9d1; break-after: avoid; text-align: left; }
h2:first-child { margin-top: 0; }
p { margin: 0 0 4pt; orphans: 3; widows: 3; }
code { font-family: "Cascadia Mono", Consolas, monospace; font-size: 9pt; background: #f1f1f5; padding: 0 2px; border-radius: 2px; }
.cmd { font-family: "Cascadia Mono", Consolas, monospace; font-size: 8.4pt; background: #f6f6f9; border: 1px solid #dcdce4; border-radius: 3px; padding: 3pt 5pt; margin: 2pt 0 4pt; text-align: left; white-space: pre-wrap; break-inside: avoid; }
em { color: #333; }
"""

BODY = """
<div class="head">
  <h1>Chanakya</h1><span class="tag">An AI teacher that works offline: narrated, animated lessons in nine languages</span>
  <p class="meta"><b>Team name:</b> The Last Commit &nbsp;·&nbsp; <b>Members:</b> Aryan Dubey, Priyadarshini Prasad, Niharika K P, Dhiraj Shetty<br>
  <b>College:</b> RV University, Bengaluru &nbsp;·&nbsp; <b>Course:</b> B.Tech (Hons) &nbsp;·&nbsp; <b>Branch:</b> Computer Science Engineering &nbsp;·&nbsp; <b>Year:</b> 2nd year<br>
  <b>Repo:</b> github.com/signingoff-dubey/UNLOX-TEACHER &nbsp;·&nbsp; <b>Version:</b> v0.16.0 &nbsp;·&nbsp; <b>Built for:</b> the Unlox hackathon</p>
</div>

<div class="cols">

<h2>Vision</h2>
<p>Quality explanation should not depend on a fast connection, a subscription or a particular language. Chanakya turns any topic into a complete video lesson on the learner&rsquo;s own device: type a question, or attach a photo or a PDF, and it plans the lesson, narrates it in the learner&rsquo;s language, animates it and lets the learner watch it, question it and take it away as an MP4 with captions. Because every model runs locally and no outside AI service is ever called, a lesson costs nothing to produce, works without internet, and keeps the learner&rsquo;s questions, photos and documents private. The same product also runs natively on an Android phone.</p>

<h2>How it works</h2>
<p>The design rests on one principle: the AI only returns <em>data</em>. A language model writes a JSON lesson that is validated against a schema, choosing one of eleven scene templates and filling in its text, while our own engine draws, times and renders every frame; nothing the model writes is ever executed. A request is first cleaned into its subject (&ldquo;teach me about dsa in java&rdquo; becomes &ldquo;DSA in Java&rdquo;), checked against what the learner already owns, and grounded in an offline knowledge base of encyclopedia articles, curated reference notes and any document the learner attached. The plan is then refined by a pipeline of specialists: a quality gate that rejects repetition and thin narration, a visual director that chooses the right scene for each idea, a writer that enriches narration, and a fact checker that verifies the statements. The approved English plan is translated, each sentence is spoken with a delivery that suits it, and every scene lasts exactly as long as its narration, so voice, captions and animation stay in sync.</p>

<h2>Capabilities</h2>
<p>Lessons range from 30 seconds to 4 minutes, and a topic can become a course of one to three videos. The eleven scene types are title, bullets, flow, cycle, compare, diagram, quiz, summary, <strong>graph</strong> (lines, parabolas, circles, ellipses, waves and more, with points, tangents and chords), <strong>code</strong> (syntax-coloured, with a highlight that follows the narration) and <strong>network</strong> (boxes and arrows for trees, linked structures and architectures). Four modes fit the purpose: Explanation, Study, Homework, which teaches the method and writes a separate answers file, and Revise, which re-teaches what the learner keeps missing. Photos of a page or a board are read by a local vision model, and PDFs of up to 2 GB are read as structured Markdown, with OCR for scans and descriptions of the pictures inside, so a lesson can teach a single chapter with page citations. Around each video sit a voice-enabled tutor that can build &ldquo;one more video&rdquo; on request, flashcards, quizzes, mind maps, glossaries, spaced-repetition review, teach-it-back grading, rewards, worksheets and question papers, MP4, caption and audio export, an offline bundle that can be shared on a USB stick, and Learnverse, a walkable 3D world generated from any topic.</p>

<h2>Flash and Pro</h2>
<p>Learners choose how a video is built. <strong>Flash</strong> starts playback within seconds and keeps writing while the learner watches, each part knowing what the earlier parts have taught. <strong>Pro</strong> plans the whole video before showing it: it outlines every scene, writes the first minute in one pass and patches each further minute on with the full outline and all earlier text in view, then gives the fact checker extra time. The result is a more coherent, carefully verified video, built with the same model as Flash.</p>

<h2>Models used</h2>
<p>All models run locally. The <strong>language model</strong> behind planning, directing, writing, fact checking, the tutor and the study tools is <strong>Qwen2.5-7B-Instruct</strong> (Q4_K_M, Apache-2.0), served by Ollama. <strong>LLaVA 7B</strong> reads photos and the pictures inside PDFs. Retrieval combines <strong>nomic-embed-text</strong> for the knowledge base, <strong>multilingual-e5-small</strong> for document passages and <strong>bge-reranker-v2-m3</strong> for re-ranking. Translation uses <strong>NLLB-200</strong> (distilled 600M), with <strong>AI4Bharat IndicTrans2</strong> as an alternative and a back-translation check on every sentence. Narration uses <strong>Piper</strong> neural voices, <strong>AI4Bharat Indic-TTS</strong> voices and <strong>Indic Parler-TTS</strong> for expressive speech. Spoken questions are understood by <strong>faster-whisper</strong>, and scanned pages are read by <strong>Tesseract</strong> and <strong>Unlimited-OCR</strong>. On Android the same roles are filled by <strong>Gemma 4 E2B</strong> (LiteRT-LM), Piper through <strong>sherpa-onnx</strong>, <strong>Whisper</strong> and <strong>Vosk</strong>, and <strong>ML Kit</strong> for translation and text recognition.</p>

<h2>Languages and voices</h2>
<p>Chanakya teaches in English, Hindi, Telugu, Marathi, Bengali, Malayalam, Tamil, Kannada and Gujarati, each with a natural voice and correctly rendered script, and the language list is configuration-driven so it can grow. Lesson length is balanced to each voice&rsquo;s speaking pace, voices fall back gracefully between engines, and every translation is verified for script and meaning before it is shown.</p>

<h2>Accuracy and trust</h2>
<p>A lesson is only as good as its facts, so every plan is checked before it is spoken. The fact checker works entirely on the device: it calculates arithmetic and equations, verifies counts and well-known lists such as the colours of the rainbow and the order of the planets, and compares each statement with passages retrieved from the knowledge base. A finding only counts when it quotes words that really appear in the source and a second, focused question agrees, and any correction must pass the same check. A <strong>memory</strong> of the learner&rsquo;s earlier videos lets new lessons build on them instead of repeating them, and technical subjects are taught with real code in the language the learner names or with a drawn diagram rather than analogy alone. Each lesson lists its sources and carries a report of what was verified or corrected.</p>

<h2>Reliability</h2>
<p>Jobs resume after interruption, heavy models share the hardware by taking turns, a graceful fallback keeps a course going if a step runs short of memory, requests to the model are retried automatically, and a built-in readiness check names anything missing and the command that fixes it. The backend is covered by 345 automated tests.</p>

<h2>Benchmarks</h2>
<p>Every figure below was measured end to end on one consumer laptop, with all models running locally and warm. <strong>Responsiveness:</strong> the time to first token is about 0.3 seconds, the first complete scene of a lesson is written in about 1.2 seconds (it was 3.2 seconds before the prompt was tailored to the subject), and the model decodes at roughly 43 tokens per second. In Flash mode the first scenes are watchable 6 to 18 seconds after the learner presses Create. <strong>Video generation:</strong> a one-minute lesson is fully built, meaning planned, checked, translated and narrated, in 40 to 70 seconds; a two-minute lesson takes two to three minutes including fact checking (about 133 seconds in Flash and 167 in Pro on a technical topic such as AVL trees); the narration of a three-minute lesson is synthesised in 10 to 17 seconds; and a three-minute MP4 at 720p renders in about 3.3 minutes. <strong>Supporting steps:</strong> knowledge-base search takes 35 to 60 milliseconds, translating 32 sentences takes 2.9 seconds, a repeated spoken question is answered in 0.29 seconds against about 10 seconds cold, a photo is accepted in 0.05 seconds so the Create button never waits, and a 1,000-page scanned PDF becomes searchable in under three minutes, with text-layer pages read in 1 to 15 milliseconds and converted to Markdown in 50 to 500 milliseconds.</p>

<h2>Approach to speed</h2>
<p>We treated latency as a design requirement and measured every change on the real models. First, we <strong>avoid constrained decoding</strong>: the schema is given to the model as text and validators repair small slips, which produced the same lesson plan in about 5 seconds instead of 12 to 22. Second, <strong>prompts are built for the subject</strong>: a general topic needs roughly 790 tokens of instructions instead of 1,700, which cut prompt processing from 0.95 to 0.30 seconds, while maths, code and diagram topics receive exactly the templates they need. Third, the plan is <strong>streamed and parsed scene by scene</strong>, so the player opens on the first finished scene while the rest is still being written. Fourth, we <strong>overlap work</strong>: finished scenes are translated while the planner is still writing, translations are batched by length (about 35% faster), and translations, narration clips and spoken-question transcripts are cached. Fifth, <strong>models stay resident while in use and are released when idle</strong>, a GPU slot lets the language model, translator and voices take turns, and a memory gate waits instead of failing. Finally, <strong>narration comes first</strong>: audio length sets scene length, so nothing is re-timed afterwards, and PDF pages that already have a text layer are read directly instead of through OCR.</p>

<h2>Technology</h2>
<p><strong>Backend:</strong> Python, FastAPI, Pydantic, SQLite, PyTorch, ONNX Runtime, Transformers, sentence-transformers, FAISS, PyMuPDF. <strong>Web:</strong> React, TypeScript, Vite, Remotion (player and MP4 renderer with Chrome and ffmpeg), three.js, Mermaid. <strong>Android:</strong> Kotlin, Jetpack Compose, Room, WorkManager, Media3. <strong>3D lessons:</strong> a headless Blender pipeline. The interface follows the team&rsquo;s Figma design.</p>

<h2>Impact</h2>
<p>A student without reliable internet gets a patient teacher in their own language. A teacher can turn a textbook chapter into a narrated video in minutes. A school can run it on its own machines with no per-use cost and no data leaving the room. Wikipedia text is used under CC BY-SA 4.0 and each lesson cites the articles it drew on; the licences of every model and voice are listed in the README.</p>

<h2>Run it</h2>
<div class="cmd">git clone https://github.com/signingoff-dubey/UNLOX-TEACHER.git
.\\setup.ps1 -Gpu     # once, online
.\\start.ps1          # http://127.0.0.1:8000</div>
<p>Requires Ollama with <code>qwen2.5:7b-instruct-q4_K_M</code>, <code>nomic-embed-text</code> and <code>llava:7b</code>. Complete documentation is in <code>Chanakya-Documentation.pdf</code>.</p>

</div>
"""


def chrome() -> str:
    for p in (r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
              r"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe", r"C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe"):
        if Path(p).exists():
            return p
    found = shutil.which("chrome") or shutil.which("google-chrome") or shutil.which("msedge")
    if not found:
        sys.exit("Google Chrome or Microsoft Edge is needed to print the PDF.")
    return found


def main(pt: float = BASE_PT) -> None:
    page = f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Chanakya: brief</title><style>{CSS % {"pt": pt}}</style></head><body>{BODY}</body></html>'
    tmp = Path(tempfile.mkdtemp(prefix="chanakya-brief-"))
    src = tmp / "brief.html"
    src.write_text(page, encoding="utf-8")
    subprocess.run([chrome(), "--headless=new", "--disable-gpu", f"--user-data-dir={tmp / 'profile'}", "--no-pdf-header-footer", "--no-sandbox",
                    f"--print-to-pdf={OUT}", src.as_uri()], check=True, timeout=300, capture_output=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"{OUT} ({OUT.stat().st_size / 1e3:.0f} KB)")


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else BASE_PT)
