# Metaverse

A walkable 3D learning world for Chanakya. A student walks a path, reads topic stations, passes a quiz gate after each one, and earns points. Points buy rides (skateboard, bicycle, hoverboard), hats, suit colours, visors, pets and perks in an in-world shop.

Everything runs in the browser with three.js. No network is needed once the app is built: fonts are bundled through `@fontsource`, and sound is synthesized with the Web Audio API.

## How it connects to Chanakya

`web/src/App.tsx` has a **Metaverse** button in the header. It lazy-loads this folder as a separate chunk and opens it full screen. When a lesson has been generated, the world is built from that lesson:

| Lesson scene (backend JSON) | World |
|---|---|
| `bullets`, `flow`, `cycle`, `compare`, `diagram` | a knowledge station (title, narration as body, items as terms) |
| `quiz` | the quiz gate after a station |
| no quiz left for a station | a generated "which idea belongs here?" question from the lesson's own items |
| `summary` narration | the finale text |

The active language tab is used, so a Hindi or Telugu lesson gives a Hindi or Telugu world. See `src/lessonToWorld.ts`.

Inside the world the learner can type any topic. The ready-made worlds (Java, photosynthesis, water cycle, and the open lesson) start at once; anything else goes to `POST /api/metaworld`, where the local model writes four stations with questions, while a "Building your world" screen shows its progress. Without a backend (`onBuild` not given) the old keyword matching and Java fallback remain.

## Layout

| Path | What |
|---|---|
| `src/Metaverse.tsx` | React component. Mounts the UI in a shadow root, so its CSS never touches the host app |
| `src/engine.ts` | The three.js engine: world, avatar, shop, input, quality scaling. Framework-free, returns a dispose function |
| `src/lessonToWorld.ts` | Backend lesson JSON to a walkable world |
| `src/ui.ts` | CSS and markup for the overlay |
| `src/types.ts` | `World`, `Zone`, `Quiz` |
| `standalone/learnverse.html` | The same experience as one self-contained HTML file (loads three.js from a CDN) |

## Run on its own

```bash
cd metaverse
npm install
npm run dev        # http://localhost:5174
npm run build      # typecheck + production build
```

## Run inside Chanakya

```bash
cd web
npm install
npm run dev        # click "Metaverse" in the header
```

`web/vite.config.ts` aliases `metaverse` to `../metaverse/src` and points `react`, `three` and `@fontsource` at `web/node_modules`, so there is one copy of each.

## Controls

Arrow keys or WASD to walk and turn, `Space` to jump, `1`-`4` to answer, `B` for the shop, `Esc` to close it. Quiz gates open their question when you reach them (no key needed); stations are read by tapping the prompt, the Open button or pressing `E`. On touch screens there is an on-screen pad with Jump and Open buttons. Points, level and purchases are saved in `localStorage` and, when a `store` is given, on the backend (`/api/metaverse/save`), so they survive another address or cleared browser data.

## Performance

Trees, lamps, crystals and clouds are instanced; fireflies animate on the GPU. The page lowers its render resolution when frames run slow, then drops from High (bloom, 2048 shadows) to Medium to Low. The Quality button switches by hand.

## Known limits

- `engine.ts` is plain JavaScript with `// @ts-nocheck`. The React wrapper and the lesson mapper are strictly typed.
- Only three worlds are hand-written. Any other topic uses the generated lesson, so create a lesson first.
- Billboard titles use Chakra Petch, which has no Indic glyphs. Indic titles fall back to the system font.
