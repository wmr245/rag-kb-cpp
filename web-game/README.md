# web-game

React + Vite + TypeScript frontend prototype for the open-world galgame direction.

## Development

Preferred workflow is Docker Compose so the frontend does not depend on local npm or node.

1. `docker compose up --build web-game`
2. Open `http://localhost:5173`

The Vite dev server proxies `/game/*` to `ai-service:8000` inside Docker.

## Local fallback

If you explicitly want to run it without Docker:

1. `cd web-game`
2. `npm install`
3. `npm run dev`

If you want to point at another API host, set `VITE_GAME_API_BASE_URL` or `VITE_DEV_PROXY_TARGET`.
