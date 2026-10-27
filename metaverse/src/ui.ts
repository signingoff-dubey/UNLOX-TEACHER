// Styles and markup for the metaverse overlay. Rendered inside a shadow root so they never touch the host app.
export const CSS = `/* Layout: full-bleed 3D world. DOM layers on top: topic card, HUD, modals, and a docked shop panel that leaves the avatar visible. */
:host{display:block;width:100%;height:100%;
  color-scheme:dark;
  --ink:#0e0a24;
  --panel:rgba(20,13,50,.74);
  --line:rgba(255,236,214,.16);
  --text:#fff2e3;
  --dim:#c9b9d9;
  --amber:#ffb454;
  --cyan:#62e6ff;
  --pink:#ff6fa8;
  --mint:#74ffb8;
  --f-d:'Chakra Petch',system-ui,sans-serif;
  --f-b:'Figtree',system-ui,sans-serif;
  --gl:max(16px,env(safe-area-inset-left,0px));
  --gr:max(16px,env(safe-area-inset-right,0px));
}
*{box-sizing:border-box}
[hidden]{display:none!important}
#app{color:var(--text);font:400 15px/1.5 var(--f-b)}
button,input{font:inherit;color:inherit}
button{cursor:pointer}
:focus-visible{outline:3px solid var(--cyan);outline-offset:2px}
#app{position:relative;height:100%;overflow:hidden;background:var(--ink)}
#gl{position:absolute;inset:0;width:100%;height:100%;display:block;touch-action:none}
.glass{background:var(--panel);border:1px solid var(--line);border-radius:14px;backdrop-filter:blur(14px) saturate(1.3);-webkit-backdrop-filter:blur(14px) saturate(1.3);box-shadow:0 10px 40px rgba(6,2,24,.45)}
.eyebrow{font:600 11px/1 var(--f-d);letter-spacing:.18em;text-transform:uppercase;color:var(--amber)}
.key{display:inline-grid;place-items:center;min-width:24px;height:24px;padding:0 6px;border:1px solid var(--line);border-bottom-width:3px;border-radius:6px;font:600 12px var(--f-d);color:var(--text);background:rgba(255,255,255,.06)}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:44px;padding:0 20px;border:0;border-radius:12px;background:var(--amber);color:#2a1300;font:700 15px var(--f-d);letter-spacing:.02em;box-shadow:0 6px 0 #b8741f;transition:transform .08s,box-shadow .08s}
.btn:hover:not(:disabled){transform:translateY(-1px)}
.btn:active:not(:disabled){transform:translateY(4px);box-shadow:0 2px 0 #b8741f}
.btn:disabled{background:rgba(255,255,255,.1);color:var(--dim);box-shadow:none;cursor:default}
.btn.ghost{background:rgba(255,255,255,.08);color:var(--text);box-shadow:0 6px 0 rgba(0,0,0,.35);border:1px solid var(--line)}
.btn.sm{min-height:36px;padding:0 14px;font-size:13px;box-shadow:0 4px 0 #b8741f}
.btn.ghost.sm{box-shadow:0 4px 0 rgba(0,0,0,.35)}
.coin{display:inline-block;width:14px;height:14px;background:#ffd25a;border:2px solid #b8741f;transform:rotate(45deg) scale(.8);vertical-align:-2px}

#topic{position:absolute;inset:0;display:grid;place-items:center;padding:24px var(--gr) 24px var(--gl);background:radial-gradient(ellipse at 50% 40%,rgba(14,10,36,.15),rgba(14,10,36,.65));transition:opacity .6s,visibility .6s}
#topic.gone{opacity:0;visibility:hidden;pointer-events:none}
.tcard{width:min(620px,100%);padding:34px 34px 28px;display:grid;gap:18px}
.tcard h1{margin:0;font:700 clamp(30px,5.4vw,46px)/1.05 var(--f-d);text-wrap:balance}
.tcard h1 span{color:var(--amber)}
.tcard p{margin:0;color:var(--dim);max-width:52ch}
.tform{display:flex;gap:10px;flex-wrap:wrap}
.tform input{flex:1 1 260px;min-width:0;height:52px;padding:0 16px;border-radius:12px;border:1px solid var(--line);background:rgba(8,4,28,.6);font-size:16px}
.tform input::placeholder{color:#8f80a8}
.chips{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.chips small{font:600 12px var(--f-d);letter-spacing:.1em;text-transform:uppercase;color:var(--dim)}
.chip{padding:6px 12px;border-radius:999px;border:1px solid var(--line);background:rgba(255,255,255,.06);font-size:14px}
.chip:hover{border-color:var(--amber)}
.legend{display:flex;flex-wrap:wrap;gap:14px;font-size:13px;color:var(--dim);align-items:center}
.legend span{display:inline-flex;gap:6px;align-items:center}
.shoprow{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap;padding:12px 14px;border-radius:12px;background:rgba(255,255,255,.05);border:1px dashed var(--line)}
.shoprow b{font:700 20px var(--f-d)}

#hud{position:absolute;inset:0;pointer-events:none;opacity:0;transition:opacity .6s}
#hud.on{opacity:1}
#hud>*{pointer-events:none}
#hud button,#hud .pad,#hud .prompt{pointer-events:auto}
.tl{position:absolute;top:16px;left:var(--gl);padding:12px 16px;display:grid;gap:4px;max-width:min(320px,52vw)}
.tl .name{font:700 20px/1.15 var(--f-d)}
.tl .zone{font-size:13px;color:var(--dim)}
.tl .req{font-size:12px;color:var(--amber)}
.tc{position:absolute;top:16px;left:50%;transform:translateX(-50%);display:flex;gap:8px;align-items:center;padding:10px 14px}
.seg{display:flex;gap:4px;padding:3px 6px;border-radius:999px;background:rgba(255,255,255,.06)}
.dot{width:10px;height:10px;border-radius:50%;border:2px solid rgba(255,255,255,.35)}
.dot.q{border-radius:3px;transform:rotate(45deg) scale(.85)}
.dot.on{background:var(--c,var(--amber));border-color:var(--c,var(--amber));box-shadow:0 0 8px var(--c,var(--amber))}
.flag{font:700 11px var(--f-d);letter-spacing:.1em;color:var(--dim)}
.tr{position:absolute;top:16px;right:var(--gr);display:grid;gap:10px;justify-items:end}
.pts{padding:10px 14px;display:grid;gap:8px;min-width:228px}
.pts .row{display:flex;gap:18px;justify-content:space-between}
.pts .lbl{display:block;font:600 10px var(--f-d);letter-spacing:.16em;text-transform:uppercase;color:var(--dim)}
.pts b{font:700 26px/1 var(--f-d);font-variant-numeric:tabular-nums}
.pts b.pop{animation:pop .5s}
.pts .ride{font:600 12px var(--f-d);color:var(--mint);min-height:16px}
@keyframes pop{40%{transform:scale(1.3);color:var(--amber)}}
.lbar{height:6px;border-radius:99px;background:rgba(255,255,255,.1);overflow:hidden}
.lbar i{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--amber),var(--pink));transition:width .5s}
#mini{width:150px;height:150px;border-radius:14px;border:1px solid var(--line);background:rgba(20,13,50,.6)}
.bl{position:absolute;left:var(--gl);bottom:calc(20px + env(safe-area-inset-bottom,0px));display:grid;gap:10px}
.prompt{display:flex;align-items:center;gap:12px;padding:10px 14px;max-width:min(380px,70vw)}
.prompt .t{font:600 15px var(--f-d)}
.pad{display:grid;grid-template-columns:repeat(3,56px);grid-template-rows:repeat(2,56px);gap:6px}
.pad button{border:1px solid var(--line);border-radius:14px;background:var(--panel);display:grid;place-items:center;touch-action:none;user-select:none;-webkit-user-select:none}
.pad button:active,.pad button.down{background:var(--amber);color:#2a1300}
.pad svg{width:22px;height:22px;fill:currentColor}
.pad .u{grid-column:2;grid-row:1}.pad .l{grid-column:1;grid-row:2}.pad .d{grid-column:2;grid-row:2}.pad .r{grid-column:3;grid-row:2}
.br .btn{flex:none}
.br{max-width:calc(100% - 232px);position:absolute;right:var(--gr);bottom:calc(20px + env(safe-area-inset-bottom,0px));display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap;justify-content:flex-end}
.act{width:72px;height:72px;border-radius:50%;border:3px solid #fff3;background:var(--amber);color:#2a1300;font:700 22px var(--f-d);box-shadow:0 6px 0 #b8741f}
.act:disabled{background:rgba(255,255,255,.1);color:var(--dim);box-shadow:none}
.float{position:absolute;pointer-events:none;font:700 24px var(--f-d);color:var(--amber);text-shadow:0 2px 12px rgba(0,0,0,.6);animation:fl 1.4s ease-out forwards}
@keyframes fl{to{transform:translateY(-60px);opacity:0}}
.toast{position:absolute;left:50%;bottom:calc(110px + env(safe-area-inset-bottom,0px));transform:translate(-50%,20px);padding:10px 18px;opacity:0;pointer-events:none;transition:.3s;font:600 14px var(--f-d);max-width:min(560px,90vw);text-align:center;z-index:30}
.toast.on{opacity:1;transform:translate(-50%,0)}

#modal{position:absolute;inset:0;display:grid;place-items:center;padding:20px var(--gr) 20px var(--gl);background:rgba(8,4,26,.55);opacity:0;visibility:hidden;transition:opacity .25s}
#modal.on{opacity:1;visibility:visible}
.card{width:min(600px,100%);max-height:100%;overflow:auto;padding:28px;display:grid;gap:16px;border-color:var(--c,var(--line));box-shadow:0 0 0 1px var(--c,transparent),0 20px 80px rgba(6,2,24,.7)}
.card h2{margin:0;font:700 28px/1.1 var(--f-d);text-wrap:balance}
.card p{margin:0;color:#ecdff4;font-size:16px;max-width:60ch}
.terms{display:flex;flex-wrap:wrap;gap:8px}
.term{padding:3px 10px;border-radius:999px;border:1px solid var(--c,var(--amber));color:var(--c,var(--amber));font:600 12px var(--f-d);letter-spacing:.06em}
.extras{display:grid;gap:8px;margin:0 0 14px;max-height:34vh;overflow:auto;padding-right:4px}
.extra{display:grid;gap:2px;padding:9px 12px;border-radius:12px;background:rgba(255,255,255,.05);border-left:3px solid var(--c,var(--amber))}
.extra b{font:700 11px var(--f-d);letter-spacing:.12em;text-transform:uppercase;color:var(--c,var(--amber))}
.extra span{font-size:14px;line-height:1.45;color:#ecdff4}
pre{margin:0;padding:12px 14px;border-radius:10px;background:#0a0620;border:1px solid var(--line);font:500 13.5px/1.55 ui-monospace,Menlo,Consolas,monospace;color:#d8f0ff;overflow-x:auto}
.opts{display:grid;gap:10px}
.opt{display:flex;align-items:center;gap:12px;min-height:50px;padding:8px 14px;text-align:left;border-radius:12px;border:1px solid var(--line);background:rgba(255,255,255,.05);font-size:16px}
.opt:hover:not(:disabled){border-color:var(--amber);background:rgba(255,180,84,.1)}
.opt.ok{border-color:var(--mint);background:rgba(116,255,184,.14)}
.opt.no{border-color:var(--pink);background:rgba(255,111,168,.12);opacity:.7}
.opt:disabled{cursor:default}
.fbk{min-height:24px;font:600 15px var(--f-d)}
.fbk.ok{color:var(--mint)}.fbk.no{color:var(--pink)}
.worth{display:flex;gap:8px;align-items:center;color:var(--dim);font-size:13px}
.cardfoot{display:flex;gap:10px;justify-content:flex-end;flex-wrap:wrap;align-items:center}
.sum{display:grid;gap:8px}
.sum div{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--line);font:600 15px var(--f-d)}
.stars{display:flex;gap:6px}
.stars svg{width:34px;height:34px}
.big{font:700 54px/1 var(--f-d);color:var(--amber);font-variant-numeric:tabular-nums}

/* shop: docked right so the avatar stays visible on the left */
#shop{position:absolute;top:0;right:0;bottom:0;width:min(450px,100%);padding:16px var(--gr) 16px 0;display:flex;flex-direction:column;transform:translateX(110%);transition:transform .45s cubic-bezier(.2,.8,.2,1);z-index:20}
#shop.on{transform:none}
.sp{flex:1;min-height:0;display:flex;flex-direction:column;overflow:hidden}
.sp-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:16px 18px 10px}
.sp-head h2{margin:0;font:700 24px var(--f-d)}
.wal{display:flex;align-items:center;gap:8px;padding:6px 12px;border-radius:999px;background:rgba(255,210,90,.14);border:1px solid rgba(255,210,90,.4);font:700 18px var(--f-d);font-variant-numeric:tabular-nums}
.tabs{display:flex;gap:6px;padding:0 18px 10px;overflow-x:auto}
.tab{flex:none;padding:7px 12px;border-radius:999px;border:1px solid var(--line);background:rgba(255,255,255,.05);font:600 13px var(--f-d)}
.tab[aria-selected="true"]{background:var(--amber);border-color:var(--amber);color:#2a1300}
.grid{flex:1;min-height:0;overflow:auto;padding:4px 18px 12px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;align-content:start}
.item{display:grid;gap:6px;justify-items:start;padding:12px;border-radius:14px;border:1px solid var(--line);background:rgba(255,255,255,.05);text-align:left}
.item:hover{border-color:var(--amber)}
.item[aria-pressed="true"]{border-color:var(--amber);background:rgba(255,180,84,.14);box-shadow:0 0 0 2px rgba(255,180,84,.35)}
.item svg{width:56px;height:56px}
.item .n{font:700 15px/1.15 var(--f-d)}
.item .d{font-size:12.5px;color:var(--dim);line-height:1.3}
.tag{margin-top:2px;padding:2px 9px;border-radius:999px;font:700 12px var(--f-d);background:rgba(255,255,255,.1);display:inline-flex;gap:6px;align-items:center}
.tag.own{background:rgba(116,255,184,.18);color:var(--mint)}
.tag.eq{background:var(--mint);color:#06301c}
.sp-foot{padding:12px 18px 16px;border-top:1px solid var(--line);display:grid;gap:10px}
.sp-foot .info{min-height:40px}
.sp-foot .info b{font:700 16px var(--f-d)}
.sp-foot .info span{display:block;font-size:13px;color:var(--dim)}
.sp-foot .row{display:flex;gap:10px}
.sp-foot .row .btn{flex:1}
#nogl{position:absolute;inset:0;display:grid;place-items:center;padding:24px;text-align:center;background:var(--ink)}

@media (max-width:760px){
  .tl{max-width:46vw;padding:10px 12px}.tl .name{font-size:16px}
  .tc{top:auto;bottom:calc(96px + env(safe-area-inset-bottom,0px))}
  #mini{width:96px;height:96px}
  .pts{min-width:0;padding:8px 10px}.pts b{font-size:20px}.pts .row{gap:12px}
  .pad{grid-template-columns:repeat(3,50px);grid-template-rows:repeat(2,50px)}
  .br .btn.sm.hm{display:none}
  .tcard{padding:24px 20px}
  .card{padding:20px}
  #shop{top:auto;height:62%;width:100%;padding:0 var(--gr) 0 var(--gl);transform:translateY(110%)}
  #shop.on{transform:none}
}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}`;

export const MARKUP = `<div id="app">
  <canvas id="gl" aria-label="3D learning world"></canvas>
  <div id="nogl" hidden><div class="glass tcard"><h1>This world needs WebGL</h1><p>Your browser could not start 3D graphics. Turn on hardware acceleration, or open the page in a recent Chrome, Edge, Firefox or Safari.</p></div></div>

  <section id="topic" aria-label="Choose a topic">
    <div class="glass tcard">
      <div class="eyebrow">Learnverse</div>
      <h1>What do you want to <span>explore</span>?</h1>
      <p>Type a concept. The world fills with stations that teach it. Read each one, pass the quiz gate, and spend your points on rides and looks.</p>
      <form class="tform" id="tform" autocomplete="off">
        <label for="q" style="position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)">Concept to learn</label>
        <input id="q" maxlength="80" placeholder="Explain me the Java concept">
        <button class="btn" type="submit">Enter the world</button>
      </form>
      <div class="chips" id="chips"><small>Worlds ready</small></div>
      <button class="btn ghost sm" id="tExit" type="button" hidden>Back to Chanakya</button>
      <div class="shoprow"><span><span class="coin"></span> <b id="tWallet">0</b> points to spend</span><button class="btn ghost sm" id="tShop" type="button">Wardrobe and shop</button></div>
      <div class="legend">
        <span><span class="key">&uarr;</span><span class="key">&larr;</span><span class="key">&darr;</span><span class="key">&rarr;</span> walk and turn</span>
        <span><span class="key">E</span> interact</span>
        <span><span class="key">B</span> shop</span>
      </div>
    </div>
  </section>

  <div id="hud">
    <div class="tl glass"><div class="eyebrow">Exploring</div><div class="name" id="hName"></div><div class="zone" id="hZone"></div><div class="req" id="hReq" hidden></div></div>
    <div class="tc glass" id="stepper" aria-label="Journey progress"></div>
    <div class="tr">
      <div class="pts glass" aria-live="polite">
        <div class="row"><div><span class="lbl">Points</span><b id="pts">0</b></div><div><span class="lbl">Level</span><b id="lvl">1</b></div><div><span class="lbl">Streak</span><b id="stk">0</b></div></div>
        <div class="lbar"><i id="lbar"></i></div>
        <div class="ride" id="rideLbl"></div>
      </div>
      <canvas id="mini" width="300" height="300" aria-label="Minimap"></canvas>
    </div>
    <div class="bl">
      <div class="prompt glass" id="prompt" hidden><span class="key">E</span><span class="t" id="promptT"></span></div>
      <div class="pad" id="pad" aria-label="Movement controls">
        <button class="u" data-k="up" aria-label="Walk forward"><svg viewBox="0 0 24 24"><path d="M12 5l8 10h-5v4H9v-4H4z"/></svg></button>
        <button class="l" data-k="left" aria-label="Turn left"><svg viewBox="0 0 24 24"><path d="M5 12l10-8v5h4v6h-4v5z"/></svg></button>
        <button class="d" data-k="down" aria-label="Walk back"><svg viewBox="0 0 24 24"><path d="M12 19l-8-10h5V5h6v4h5z"/></svg></button>
        <button class="r" data-k="right" aria-label="Turn right"><svg viewBox="0 0 24 24"><path d="M19 12L9 4v5H5v6h4v5z"/></svg></button>
      </div>
    </div>
    <div class="br">
      <button class="btn ghost sm hm" id="bSound" aria-pressed="true">Sound on</button>
      <button class="btn ghost sm hm" id="bQual">Quality: High</button>
      <button class="btn ghost sm hm" id="bTopic">New topic</button>
      <button class="btn ghost sm" id="bExit" hidden>Exit</button>
      <button class="btn sm" id="bShop">Shop <span class="key" style="margin-left:4px">B</span></button>
      <button class="act" id="bAct" disabled aria-label="Interact">E</button>
    </div>
    <div class="toast glass" id="toast" role="status"></div>
  </div>

  <div id="modal" role="dialog" aria-modal="true"><div class="card glass" id="card"></div></div>

  <aside id="shop" aria-label="Shop and wardrobe"><div class="sp glass">
    <div class="sp-head"><h2>Wardrobe and shop</h2><div class="wal"><span class="coin"></span><span id="sWallet">0</span></div></div>
    <div class="tabs" id="tabs" role="tablist"></div>
    <div class="grid" id="grid"></div>
    <div class="sp-foot"><div class="info" id="sInfo"></div><div class="row"><button class="btn" id="sAct" disabled>Select an item</button><button class="btn ghost" id="sClose">Done</button></div></div>
  </div></aside>
</div>`;
