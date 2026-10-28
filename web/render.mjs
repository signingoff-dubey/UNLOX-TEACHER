// Renders one lesson track to MP4 with Remotion. Called by backend/app/exporter.py:
//   node render.mjs <props.json> <out.mp4> [concurrency]
//   node render.mjs --bundle-only        (pre-build the bundle so the first export is fast)
// Progress lines ("PROGRESS <stage> <0..1>") are parsed by the backend.
import fs from "node:fs";
import path from "node:path";
import { bundle } from "@remotion/bundler";
import { ensureBrowser, renderMedia, selectComposition } from "@remotion/renderer";

const ENTRY = path.resolve("src/remotion/index.ts");
const BUNDLE_DIR = path.resolve(".remotion-bundle");
// Design canvas is 1920x1080; RENDER_HEIGHT scales the output (720 -> 1280x720 = the spec's 720p, default; 1080 = native; set per export by the backend).
const OUT_HEIGHT = Number(process.env.RENDER_HEIGHT || 720);
const progress = (stage, value) => console.log(`PROGRESS ${stage} ${value.toFixed(3)}`);

const newestMtime = (dir) =>
  fs.readdirSync(dir, { withFileTypes: true }).reduce((max, e) => {
    const p = path.join(dir, e.name);
    return Math.max(max, e.isDirectory() ? newestMtime(p) : fs.statSync(p).mtimeMs);
  }, 0);

async function getBundle() {
  const index = path.join(BUNDLE_DIR, "index.html");
  const fresh = fs.existsSync(index) && fs.statSync(index).mtimeMs > newestMtime(path.resolve("src"));
  if (fresh) return BUNDLE_DIR;
  progress("bundling", 0.0);
  let shown = -1;
  return bundle({
    entryPoint: ENTRY, outDir: BUNDLE_DIR,
    onProgress: (p) => {                                      // 0-100: the real bundling progress (the first export after a code change)
      const pct = Math.floor(p);
      if (pct !== shown) { shown = pct; progress("preparing_the_video_templates", 0.04 * (p / 100)); }
    },
  });
}

const [, , propsFile, outFile, concurrency] = process.argv;

if (propsFile === "--bundle-only") {
  await getBundle();
  await ensureBrowser();
  console.log("Bundle and browser ready:", BUNDLE_DIR);
  process.exit(0);
}

const inputProps = JSON.parse(fs.readFileSync(propsFile, "utf8"));
const serveUrl = await getBundle();
progress("preparing", 0.04);
await ensureBrowser();
const composition = await selectComposition({ serveUrl, id: "Lesson", inputProps });

let last = -1;
await renderMedia({
  composition,
  serveUrl,
  codec: "h264",
  scale: OUT_HEIGHT / composition.height,
  outputLocation: outFile,
  inputProps,
  concurrency: concurrency ? Number(concurrency) : null,
  onProgress: ({ progress: p }) => {
    const pct = Math.floor(p * 100);
    if (pct !== last) {
      last = pct;
      progress("rendering", 0.05 + 0.95 * p);
    }
  },
});
console.log("Wrote", outFile);
