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
