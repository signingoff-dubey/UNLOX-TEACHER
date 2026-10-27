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
  progress("bundling", 0.02);
  return bundle({ entryPoint: ENTRY, outDir: BUNDLE_DIR });
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
