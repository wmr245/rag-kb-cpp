# web-game

React + Vite + TypeScript frontend for the assistant-centric personal AI workspace.

## Development

Preferred workflow is Docker Compose so the frontend does not depend on local npm or node.

1. `docker compose up --build web-game`
2. Open `http://localhost:5173`

The Vite dev server proxies `/game/*` to `ai-service:8000` inside Docker.

## Full-chain regression

The primary frontend acceptance path is now the assistant workspace regression:

1. Start the stack so `web-game` can reach `/game/*`
2. Run `npm run regression:assistant-workspace`

This regression validates the assistant-centric path end-to-end:

- import or discover seed content
- select a projected assistant
- activate the assistant through `POST /game/assistants`
- create the first conversation segment
- send a message and render speech/narration
- open the right drawer and verify long-memory visibility
- archive the first snapshot
- create a second segment and verify recall-compatible long-memory state

Artifacts are written under `web-game/output/assistant-workspace-regression/`.

## Local fallback

If you explicitly want to run it without Docker:

1. `cd web-game`
2. `npm install`
3. `npm run dev`

If you want to point at another API host, set `VITE_GAME_API_BASE_URL` or `VITE_DEV_PROXY_TARGET`.
