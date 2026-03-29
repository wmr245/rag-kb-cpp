Original prompt: 先把内容导入链路做扎实。重点不是更好看，而是更可靠。可以补：JSON 基本校验和错误定位、导入前预检、导入成功后的明确反馈、worldbook / character card 最小示例库，相关入口在 SeedImportModal.tsx

2026-03-28
- Started tightening the web-game seed import flow around `SeedImportModal.tsx`.
- Current focus: local draft validation, preflight summaries, clearer success feedback, and expandable starter packs.
- Added `web-game/src/lib/importValidation.ts` for local JSON parsing, line/column reporting, and worldbook/character cross-checks.
- Expanded starter content into a small library (`雨后校园`, `月幕书店`) and wired starter-pack selection into the modal.
- Seed import modal now shows preflight status, issue lists, starter-pack choices, and blocks import until blocking issues are fixed.
- App import flow now refreshes known character ids for duplicate checks and shows a success banner after import completes.
- Verification so far: `tsc --noEmit` and `vite build` pass.
- Added local Playwright support to `web-game` plus `npm run regression:import`.
- Added `web-game/scripts/run-import-regression.mjs` to open the import modal, verify the preflight block, capture a screenshot, and write a JSON summary.
- Browser regression output currently lands in `web-game/output/import-regression/` and the latest summary reports `预检通过`, `canImport: true`, `issueCount: 0`, and no console errors.

2026-03-28
- Shifted from import-only UI work into session-workspace behavior: recent session restore, import-to-opening guidance, and richer session rail interactions.
- Added `web-game/src/lib/sessionWorkspace.ts` to persist selected worldbook, recent session per worldbook, and import launch cues for future long-lived memory flows.
- `App.tsx` now resolves preferred worldbook/session on bootstrap, restores scoped sessions when switching worlds, auto-guides into session creation after a fresh import, and keeps session titles distinct (`夜1`, `夜2`, ...).
- `SessionRail.tsx` now surfaces a launch cue card, a continue-recent-session card, and richer per-session metadata.
- `SessionComposerModal.tsx` now frames each new session as an independent memory line, preparing for longer session lifecycles.

2026-03-28
- Added session lifecycle management across backend and frontend: sessions can now be renamed, archived, restored, and excluded from turn submission while archived.
- `SessionRail` now separates active vs archived memory lines, supports inline rename and lifecycle actions, and keeps the recent-session restore card scoped to active sessions.
- `SceneInspector` now includes a lightweight memory timeline so the right drawer shows how memories accumulate over time.
- Browser regression now covers rename -> archive -> restore -> reload session recovery, and the import regression still passes afterward.

2026-03-28
- Added long-memory design and next-phase planning docs under guidance, and removed the old `.gitignore` block on `guidance/` so these documents can be versioned.
- Added a session-workspace lifecycle note plus a notes index to keep the project docs easier to navigate.

2026-03-28
- Shifted into long-memory MVP validation and anti-repetition tuning for the web-game character dialogue flow.
- Updated the starter/sample Lin Xi definition to use cadence/style cues instead of explicit habit phrases, but discovered the live `game-data/character_cards/lin_xi.json` file is owned by `nobody:nogroup`, so runtime data must be refreshed through the app/container path instead of a normal file edit.
- Hardened `character_response_service.py` so habit phrases are optional style cues, recently repeated catchphrases are avoided, and LLM drafts that reuse them are retried.
- Real end-to-end API testing surfaced a turn-time 500: the router was already returning `longMemory`, but `GameTurnResponse` was missing the `longMemory` field and Pydantic rejected the response payload.
- Fixed the response-model mismatch by adding `longMemory` to `GameTurnResponse`, restarted `ai-service`, and refreshed the live `lin_xi` card through the container so runtime data now uses cadence hints with no `habitPhrases`.
- Verified a real create -> 3 turns -> archive -> new session -> recall flow against `http://localhost:8000`: no repeated `也许吧 / 你别多想`, archive promotion returned `promotedCount=5`, the new session loaded a long-term profile summary, and the recall turn included `longMemory.selectedItems`.
- Verified PostgreSQL persistence for the archived session: `game_memories` stored 5 rows for `sess_cb51ecb8492a`, and `game_memory_profiles` updated `lin_xi` to `trust=14, affection=7, tension=0`.

2026-03-28
- Implemented the “de-template + long-memory presentation split” pass.
- Prompt input now uses a dedicated prompt digest that excludes director notes, while debug output still keeps the full recent-turn digest.
- Relaxed the LLM prompt away from rigid sentence-count constraints and added anti-pattern guidance plus a retry path for overformatted replies.
- Split long-memory API fields into retrieval-facing vs UI-facing summaries, generated human-readable `displaySummary` / `displayTeaser` values, and added write-time + read-time dedupe to reduce repeated `event/promise` memories.
- `SceneInspector` now frames the relationship area as “关系卡”, keeps long memory collapsed by default, and renders only display summaries in the long-memory timeline.
- Real API validation after these changes: archive promotion for a fresh test session dropped to `promotedCount=2` after dedupe, archive/recall long-memory items were no longer duplicated, and UI-facing long-memory strings became readable Chinese summaries instead of raw retrieval templates.
- Frontend verification: `tsc --noEmit` and `vite build` pass. The legacy session-workspace Playwright regression still has unrelated assumptions about visible session rows/drawer state; I patched one scrim issue, but the broader script remains flaky and should be rewritten as a more focused smoke/regression for the current session rail.

2026-03-28
- Reworked the visible turn flow from “single character reply + director note” into “speech + narration”.
- Backend now returns structured character beats via `primaryDialogue` / `primaryNarration`, while `primaryReply` remains as a compatibility fallback.
- `state_update_service.py` no longer appends `director` turns into `session.recentTurns`; character output is stored as up to two turns: narration first, then speech.
- Prompt construction in `character_response_service.py` now requests JSON-only structured output, keeps narration limited to动作/神态/心理, and strips leftover leading ellipses during normalization. If the retry draft is still overformatted, it falls back to the deterministic heuristic reply.
- `memory_retrieval_service.py` now excludes character narration from prompt-turn digests, so model context only sees player text plus spoken character lines.
- Frontend `DialogueStage` now hides legacy director turns, renders narration with a lighter bubble treatment, and `TurnSpotlight` now shows speech plus optional narration instead of a director block.
- Main stage/session UI copy was updated away from “导演” language so the internal planner no longer reads as a visible actor.
- Verification:
  - `python3 -m compileall python-ai/app`
  - `node node_modules/typescript/bin/tsc -p tsconfig.json --noEmit` in `web-game/`
  - `node node_modules/vite/bin/vite.js build --outDir /tmp/rag-web-game-dist-dialogue-split` in `web-game/`
  - Real `ai-service` function flow inside Docker: `create session -> play_turn -> archive -> create new session -> recall`. The first turn returned separate narration/speech fields, `session.recentTurns` contained no `director` rows, archive promotion still worked, and recall still selected long-memory items.

2026-03-28
- Investigated a user-facing `unexpected game service error` banner and found the visible failure was tied to the running service state, not the new dialogue/narration schema itself. After restarting `ai-service` and `web-game`, `GET /game/sessions` returned `200` again.
- Added a standalone end-to-end report at `guidance/2026-03-28-dialogue-narration-e2e-report.md`.
- Real HTTP route validation now covers `POST /sessions -> POST /turns -> PATCH archive -> POST /sessions -> POST /turns`, all returning `200`, with separated `primaryDialogue` / `primaryNarration`, successful archive promotion, and non-empty long-memory recall selection.
- Browser smoke validation now confirms: app load succeeds, no red unexpected-error banner appears on load, a real session can be opened, a turn can be submitted from the UI, and narration/speech bubbles both render in the dialogue stage.
- Remaining browser instability is concentrated in side-drawer automation: the session-rail archive button and relation drawer are still awkward to drive reliably because the drawer/scrim interaction model intercepts Playwright clicks.

2026-03-28
- Added `guidance/2026-03-28-dialogue-long-memory-improvement-directions.md` to capture the latest dialogue-generation lessons, the case for layered long-memory retrieval, and the next prompt/retrieval iteration directions after the 10-turn real-chain validation.
- Added `guidance/2026-03-28-prompt-iteration-next-prompt.md` so the next handoff prompt explicitly treats prompt iteration as the highest-priority task, with memory-index design as the secondary line.

2026-03-29
- Added `guidance/2026-03-29-personal-assistant-direction.md` to document the new product-level direction: shrink the project from a multi-timeline interactive narrative shell into a personal AI assistant while keeping worldbook as background, character card as persona, narration as a low-frequency expression layer, and long memory as assistant-bound memory.
- Added `guidance/2026-03-29-next-prompt.md` so the next handoff explicitly prioritizes the `assistant`-centric product model, major frontend information-architecture changes, and backend memory-ownership refactors over continuing the old session/timeline framing.
- Added `guidance/2026-03-29-personal-assistant-task-breakdown.md` to turn the new direction into an executable backlog, with detailed tasks across frontend IA, assistant modeling, memory ownership, migration, retrieval layering, and validation.

2026-03-29
- Continued the assistant-centric frontend tightening from “real assistant list + assistantId-aware sessions” into a complete activation flow for UI testing.
- `App.tsx` now tracks `activatingAssistantId`, activation-specific success/error messages, and calls `POST /game/assistants` so projected assistants can be explicitly activated from the frontend before opening a new conversation segment.
- `AssistantRail.tsx` now marks projected assistants as `待启用`, exposes per-row `启用助手`, and changes the main CTA so projected assistants must be activated before the user can create a new segment.
- `SessionComposerModal.tsx` and the message composer now expose stable `data-testid` hooks for the new assistant-centric regression.
- Added `web-game/scripts/run-assistant-workspace-regression.mjs` plus `npm run regression:assistant-workspace` as the new primary frontend acceptance path, covering projected assistant selection, assistant activation, segment creation, messaging, drawer visibility, archive, second-segment recall, and archived snapshot persistence.
- Updated `web-game/README.md` and `guidance/2026-03-29-assistant-phase-1-implementation.md` so the documented validation path is now assistant full-chain regression instead of the old session-workspace smoke.

2026-03-29
- Fixed a backend compatibility bug on archive promotion: `long_memory_service.py` now upserts `game_memory_profiles` against both the new assistant-scoped identity and the legacy worldbook/profile primary key, so assistant-centric archive flows no longer fail on older databases.
- Verified the archived-session path directly in `ai-service`: `update_game_session(..., status='archived')` now succeeds and returns a non-empty `ArchivePromotionSummary`.
- Ran the new real Playwright acceptance flow inside Docker with `node ./scripts/run-assistant-workspace-regression.mjs`; the generated `summary.json` reported `activatedAssistant`, `createdFirstSession`, `messageSent`, `renderedNarration`, `longMemoryVisibleAfterFirstTurn`, `archivedFirstSession`, `archivedSnapshotVisible`, `createdSecondSession`, and `longMemoryVisibleAfterRecall` all successful, with no console errors.
