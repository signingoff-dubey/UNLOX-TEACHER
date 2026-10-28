"""A lesson as one file you can carry on a USB stick: `.chanakya.zip` holds the lesson (JSON), every narration recording, the captions and
`player.html`, a small player that runs in any browser with no server and no internet (double-click it). Import puts the lesson back
into another computer's Chanakya, so teachers can share lessons without a network."""
from __future__ import annotations

import json
import re
import uuid
import zipfile
from pathlib import Path

from . import config
from .pipeline import LESSONS_DIR, load_lesson

MAX_BYTES = 400 * 1024 * 1024
_AUDIO = re.compile(r"^[A-Za-z0-9_.-]{1,120}\.wav$")
_SRT = re.compile(r"^captions_[a-z]{2}\.srt$")
_ID = re.compile(r"^[a-z0-9]{4,32}$")


class BundleError(ValueError):
    pass


def _audio_name(url: str) -> str:
    return Path(url).name


def export_bundle(lesson_id: str, lessons_dir: Path | None = None, audio_dir: Path | None = None) -> Path:
    """Builds (or rebuilds) `<id>.chanakya.zip` next to the lesson and returns its path."""
    lessons_dir = lessons_dir or LESSONS_DIR
    audio_dir = audio_dir or (config.MEDIA_DIR / "audio")
    lesson = json.loads((lessons_dir / lesson_id / "lesson.json").read_text(encoding="utf-8"))
    if lesson.get("building"):
        raise BundleError("This lesson is still being made. Export it when it is finished.")
    out = lessons_dir / lesson_id / f"{lesson_id}.chanakya.zip"
    names: list[str] = []
    portable = json.loads(json.dumps(lesson))
    for track in portable["languages"].values():
        for s in track["scenes"]:
            if s.get("audio_url"):
                name = _audio_name(s["audio_url"])
                s["audio_url"] = f"audio/{name}"
                if name not in names:
                    names.append(name)
    portable.pop("videos", None)
    portable["pending"] = []
    from . import cache
    key = cache.key_of(portable)                       # everything that goes into the file; the list of MP4s does not
    if cache.is_fresh(out, key):
        return out                                     # made before from this very lesson: no second zip
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps({"format": "chanakya-bundle", "version": 1, "lesson_id": lesson_id, "concept": lesson.get("concept", ""),
                                                "languages": list(portable["languages"])}, ensure_ascii=False))
        z.writestr("lesson.json", json.dumps(portable, ensure_ascii=False))
        for name in names:
            f = audio_dir / name
            if f.exists():
                z.write(f, f"audio/{name}")
        for srt in (lessons_dir / lesson_id).glob("captions_*.srt"):
            z.write(srt, srt.name)
        z.writestr("player.html", player_html(portable))
        z.writestr("README.txt", f"Chanakya lesson: {lesson.get('concept', '')}\n\nOpen player.html in any browser to watch it (no internet needed).\n"
                                 "To add it to another Chanakya: Library > Import a lesson, and choose this file.\n")
    cache.mark(out, key)
    return out


def import_bundle(data: Path, lessons_dir: Path | None = None, audio_dir: Path | None = None) -> str:
    """Reads a `.chanakya.zip` and adds its lesson here. Returns the new lesson's id. Only the files a bundle should hold are accepted."""
    lessons_dir = lessons_dir or LESSONS_DIR
    audio_dir = audio_dir or (config.MEDIA_DIR / "audio")
    try:
        z = zipfile.ZipFile(data)
    except zipfile.BadZipFile as e:
        raise BundleError("That is not a Chanakya bundle.") from e
    with z:
        infos = {i.filename: i for i in z.infolist()}
        if sum(i.file_size for i in infos.values()) > MAX_BYTES:
            raise BundleError("The bundle is too large.")
        if "lesson.json" not in infos or "manifest.json" not in infos:
            raise BundleError("That is not a Chanakya bundle.")
        try:
            manifest = json.loads(z.read("manifest.json"))
            lesson = json.loads(z.read("lesson.json"))
        except ValueError as e:
            raise BundleError("The bundle is damaged.") from e
        if manifest.get("format") != "chanakya-bundle" or not isinstance(lesson.get("languages"), dict) or not lesson["languages"]:
            raise BundleError("That is not a Chanakya bundle.")
        new_id = lesson.get("id", "")
        if not _ID.match(str(new_id)) or (lessons_dir / new_id / "lesson.json").exists():
            new_id = uuid.uuid4().hex[:10]                                # never overwrite a lesson that is already here
        audio_dir.mkdir(parents=True, exist_ok=True)
        for name, info in infos.items():
            if name.startswith("audio/") and _AUDIO.match(name[6:]) and not info.is_dir():
                (audio_dir / name[6:]).write_bytes(z.read(name))
        folder = lessons_dir / new_id
        folder.mkdir(parents=True, exist_ok=True)
        for name in infos:
            if _SRT.match(name):
                (folder / name).write_bytes(z.read(name))
        for track in lesson["languages"].values():
            for s in track.get("scenes", []):
                if s.get("audio_url"):
                    s["audio_url"] = f"/media/audio/{_audio_name(s['audio_url'])}"
        lesson.update(id=new_id, videos={}, pending=[], failed=[], imported=True)
        lesson.pop("building", None)
        (folder / "lesson.json").write_text(json.dumps(lesson, ensure_ascii=False, indent=1), encoding="utf-8")
    return new_id


# ------------------------------------------------------------------ the standalone player
def player_html(lesson: dict) -> str:
    data = json.dumps(lesson, ensure_ascii=False).replace("</", "<\\/")
    return _PLAYER.replace("__DATA__", data).replace("__TITLE__", _esc(lesson.get("concept", "Chanakya lesson")))


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


_PLAYER = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>__TITLE__</title>
<style>
:root{--bg:#e2e2e2;--ink:#1c1c1c;--muted:#6b6b6b;--card:#f6f6f6;--line:#d6d6d6;--lime:#c7d43d;--c0:#e06a1b;--c1:#2f8335;--c2:#4a86c5;--c3:#e0457a;--c4:#7a62c9;--c5:#2e9aa0}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:"Noto Sans","Noto Sans Devanagari","Noto Sans Telugu","Nirmala UI",system-ui,sans-serif}
main{max-width:1040px;margin:0 auto;padding:16px}h1{font-size:22px;margin:6px 0 12px}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px}.tabs button,.ctl button{border:0;border-radius:99px;padding:8px 14px;background:#fff;font:600 14px inherit;cursor:pointer}
.tabs button.on{background:var(--ink);color:#fff}
.stage{position:relative;aspect-ratio:16/9;background:var(--bg);border-radius:20px;overflow:hidden;box-shadow:0 10px 30px rgba(0,0,0,.12);border:3px solid #fff}
.scene{position:absolute;inset:0;padding:5% 6%;display:flex;flex-direction:column;gap:2.2%}.scene h2{margin:0;font-size:clamp(20px,4.2vw,46px);line-height:1.2}
.scene h2::after{content:"";display:block;height:6px;width:120px;background:var(--c0);border-radius:3px;margin-top:10px}
.title{align-items:center;justify-content:center;text-align:center}.title h2{font-size:clamp(26px,6vw,64px)}.title h2::after{margin:12px auto 0}
.list{display:flex;flex-direction:column;gap:1.6%}.it{background:var(--card);border:3px solid #fff;border-radius:22px;padding:1.4% 3%;font-weight:600;font-size:clamp(14px,2.6vw,30px);display:flex;gap:16px;align-items:center;opacity:0;transform:translateX(-40px);transition:all .45s cubic-bezier(.2,.8,.2,1)}
.it.in{opacity:1;transform:none}.n{flex:none;width:2em;height:2em;border-radius:50%;color:#fff;display:grid;place-items:center;font-weight:800}
.row{display:flex;gap:2%;align-items:stretch;flex-wrap:wrap}.row .it{flex:1;flex-direction:column;justify-content:center;text-align:center;min-width:22%}
.cols{display:flex;gap:3%}.cols>div{flex:1;background:var(--card);border-radius:22px;overflow:hidden;border:3px solid #fff}.cols b{display:block;color:#fff;padding:2% 4%;font-size:clamp(16px,2.8vw,32px)}
.cols .it{border:0;border-radius:0;background:none;opacity:0}.cols .it.in{opacity:1}
.quiz .it.ok.in{background:#dcf1e3;border-color:var(--c1)}
.code{background:#1b2338;color:#e8ecf5;border-radius:18px;padding:2%;font:clamp(12px,2.2vw,24px) ui-monospace,Consolas,monospace;white-space:pre}.code div{padding:.15em .6em;border-left:6px solid transparent}.code .on{background:rgba(233,138,46,.2);border-color:var(--c0)}
.eq{background:var(--ink);color:#fff;padding:1% 3%;border-radius:16px;font-size:clamp(16px,3vw,34px);text-align:center;align-self:flex-start}
.cap{position:absolute;left:5%;right:5%;bottom:3%;text-align:center}.cap span{background:rgba(0,0,0,.6);color:#fff;padding:.3em .8em;border-radius:10px;font-size:clamp(12px,2vw,22px)}
svg.net{width:100%;height:100%}
.ctl{display:flex;gap:10px;align-items:center;margin:12px 0}.ctl input{flex:1}.time{font-variant-numeric:tabular-nums;color:var(--muted);font-size:13px;min-width:90px;text-align:right}
ol{list-style:none;padding:0;margin:8px 0;display:grid;gap:6px}ol button{width:100%;text-align:left;border:0;border-radius:14px;padding:10px 14px;background:#fff;font:600 14px inherit;cursor:pointer}ol button.on{outline:3px solid var(--ink)}
</style></head><body><main>
<h1 id="t"></h1><div class="tabs" id="tabs"></div>
<div class="stage" id="stage"></div>
<div class="ctl"><button id="prev" aria-label="Previous scene">&#9664;&#9664;</button><button id="play">Play</button><button id="next" aria-label="Next scene">&#9654;&#9654;</button><input id="seek" type="range" min="0" max="1000" value="0" aria-label="Seek"><span class="time" id="time"></span><button id="cc">Captions</button></div>
<ol id="list"></ol></main>
<script id="lesson" type="application/json">__DATA__</script>
<script>
const L=JSON.parse(document.getElementById('lesson').textContent);let lang=Object.keys(L.languages)[0],idx=0,cc=true,audio=new Audio(),playing=false;
const C=['var(--c0)','var(--c1)','var(--c2)','var(--c3)','var(--c4)','var(--c5)'],$=id=>document.getElementById(id);
const T=()=>L.languages[lang],S=()=>T().scenes[idx],esc=s=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
function reveal(n,total){const sp=S().speech_s||S().duration_s||5;return(i)=>(audio.currentTime||0)>=.3+i*sp*.78/Math.max(total,1)}
function draw(){const s=S(),st=$('stage');let h='';const items=s.items||[];const t=s.template;
 const num=i=>`<span class="n" style="background:${C[i%6]}">${i+1}</span>`;
 if(t==='title')h=`<div class="scene title"><h2>${esc(s.heading)}</h2></div>`;
 else if(t==='flow'||t==='cycle'||t==='diagram')h=`<div class="scene"><h2>${esc(s.heading)}</h2><div class="row">${items.map((x,i)=>`<div class="it" data-i="${i}" style="border-color:${C[i%6]}">${num(i)}${esc(x)}</div>`).join('')}</div></div>`;
 else if(t==='compare')h=`<div class="scene"><h2>${esc(s.heading)}</h2><div class="cols">${[[s.left_title,s.left,'--c2'],[s.right_title,s.right,'--c0']].map(([a,b,c],k)=>`<div><b style="background:var(${c})">${esc(a||'')}</b>${(b||[]).map((x,i)=>`<div class="it" data-i="${k*10+i}">${esc(x)}</div>`).join('')}</div>`).join('')}</div></div>`;
 else if(t==='quiz')h=`<div class="scene quiz"><h2>${esc(s.heading)}</h2><div class="row">${items.map((x,i)=>`<div class="it${i===s.answer_index?' ok':''}" data-i="${i}">${String.fromCharCode(65+i)}. ${esc(x)}</div>`).join('')}</div></div>`;
 else if(t==='code')h=`<div class="scene"><h2>${esc(s.heading)}</h2><div class="code">${(s.code||[]).map((x,i)=>`<div data-l="${i}">${esc(x)}</div>`).join('')}</div>${(s.output||[]).length?`<div class="code">${s.output.map(o=>'&gt; '+esc(o)).join('<br>')}</div>`:''}</div>`;
 else if(t==='graph')h=`<div class="scene"><h2>${esc(s.heading)}</h2>${s.equation?`<div class="eq">${esc(s.equation)}</div>`:''}<div class="list">${items.map((x,i)=>`<div class="it" data-i="${i}">${num(i)}${esc(x)}</div>`).join('')}</div></div>`;
 else if(t==='network'&&s.positions&&s.positions.length){const P=s.positions;h=`<div class="scene"><h2>${esc(s.heading)}</h2><svg class="net" viewBox="0 0 1000 420"><defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10z" fill="#6b6b6b"/></marker></defs>${(s.edges||[]).map(e=>`<line x1="${P[e.src][0]}" y1="${P[e.src][1]}" x2="${P[e.dst][0]}" y2="${P[e.dst][1]}" stroke="#6b6b6b" stroke-width="4" marker-end="url(#a)"/>`).join('')}${(s.nodes||[]).map((n,i)=>`<g><rect x="${P[i][0]-80}" y="${P[i][1]-26}" width="160" height="52" rx="14" fill="#fff" stroke="${C[i%6]}" stroke-width="4"/><text x="${P[i][0]}" y="${P[i][1]+7}" text-anchor="middle" font-size="22" font-weight="700">${esc(n)}</text></g>`).join('')}</svg></div>`}
 else h=`<div class="scene"><h2>${esc(s.heading)}</h2><div class="list">${items.map((x,i)=>`<div class="it" data-i="${i}">${num(i)}${esc(x)}</div>`).join('')}</div></div>`;
 st.innerHTML=h+`<div class="cap" id="cap">${cc?'<span>'+esc(s.narration)+'</span>':''}</div>`;
 const hl=(s.highlights||[]);tick()}
function tick(){const s=S(),els=[...document.querySelectorAll('#stage .it')],n=els.length,r=reveal(0,n);els.forEach((e,i)=>e.classList.toggle('in',!playing&&!audio.currentTime||r(i)));
 const lines=[...document.querySelectorAll('#stage .code [data-l]')],hs=s.highlights||[];if(lines.length){let a=-1;hs.forEach((l,k)=>{if(reveal(0,hs.length)(k))a=l});lines.forEach((e,i)=>e.classList.toggle('on',i===a))}
 const total=T().duration_s||1,at=(S().start_s||0)+(audio.currentTime||0);$('seek').value=Math.round(at/total*1000);$('time').textContent=fmt(at)+' / '+fmt(total)}
const fmt=x=>Math.floor(x/60)+':'+String(Math.floor(x%60)).padStart(2,'0');
function load(i,autoplay){idx=Math.max(0,Math.min(i,T().scenes.length-1));audio.pause();const s=S();audio=new Audio(s.audio_url||'');audio.onended=()=>{if(idx<T().scenes.length-1)load(idx+1,true);else{playing=false;$('play').textContent='Play'}};draw();renderList();if(autoplay){audio.play().catch(()=>{});playing=true;$('play').textContent='Pause'}}
function renderList(){$('list').innerHTML=T().scenes.map((s,i)=>`<li><button class="${i===idx?'on':''}" onclick="load(${i},true)">${i+1}. ${esc(s.heading)}</button></li>`).join('')}
function tabs(){$('tabs').innerHTML=Object.values(L.languages).map(t=>`<button class="${t.lang===lang?'on':''}" onclick="lang='${t.lang}';tabs();load(0,false)">${esc(t.native||t.name)}</button>`).join('')}
$('t').textContent=L.concept;$('play').onclick=()=>{if(playing){audio.pause();playing=false;$('play').textContent='Play'}else{audio.play().catch(()=>{});playing=true;$('play').textContent='Pause'}};
$('prev').onclick=()=>load(idx-1,playing);$('next').onclick=()=>load(idx+1,playing);$('cc').onclick=()=>{cc=!cc;draw()};
$('seek').oninput=e=>{const t=e.target.value/1000*(T().duration_s||1);let k=T().scenes.findIndex(s=>t>=s.start_s&&t<s.start_s+s.duration_s);if(k<0)k=T().scenes.length-1;load(k,playing);audio.addEventListener('loadedmetadata',()=>{audio.currentTime=Math.max(0,t-S().start_s)},{once:true})};
setInterval(tick,120);tabs();load(0,false);
</script></body></html>"""
