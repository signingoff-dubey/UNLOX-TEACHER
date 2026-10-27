# RootLens dashboard

React 19, Vite and Tailwind 4 front end for the RootLens API. Every screen reads live data from the FastAPI backend; nothing is mocked.

## Run

```bash
npm install
cp .env.example .env     # optional: sets VITE_API_URL (default http://127.0.0.1:8000)
npm run dev              # http://localhost:5173
npm run build
npm test
```

Start the API first (`make api` in the backend repo). The API address can also be changed in Settings > Data.

## Screens and endpoints

| Screen | Endpoints |
|--------|-----------|
| Overview | `/api/overview`, `/api/metrics`, `/api/ranking`, `/api/runs` |
| Ranking | `/api/ranking`, `/api/safe-windows` |
| Safe windows | `/api/safe-windows` |
| Savings | `/api/savings/default`, `POST /api/savings`, `/api/safe-windows` |
| AI Analyst | `/api/ai/status`, `POST /api/ai/ask`, `POST /api/ai/investigate`, `/api/runs` |
| Validation | `/api/validation/planted`, `/api/validation/ai4i` |
| Timeline | `/api/timeline` |
| Stations (Bosch) | `/api/stations` |
| Pilot planner | `/api/pilots`, `POST /api/pilot`, `/api/safe-windows` |
| How we compare | `/api/compare` |
| Captures | `/api/captures`, `POST /api/captures`, `POST /api/captures/manual`, `/api/captures/{id}`, `/api/run-sheet`, `/api/run-sheet/fields`, `/api/runs`, `/api/runs/{index}` |
| Inspection | `/api/inspection`, `/api/inspection/samples`, `POST /api/inspection/scan`, `POST /api/inspection/samples/analyze`, `/api/inspection/{id}`, `/api/inspection/{id}/model.glb` |
| Summary panel | `/api/overview`, `/api/runs` |
| Navbar | `/api/health`, `/api/overview` |

A 503 from the API means the artifact has not been generated yet; the screen says so and offers a retry.
