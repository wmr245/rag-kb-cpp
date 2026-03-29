# 2026-03-28 Dialogue + Narration E2E Report

## Scope

Validate the post-change conversation flow after removing the visible director layer and splitting character replies into:

- `primaryDialogue`
- `primaryNarration`

This report combines:

- browser/UI smoke validation
- real HTTP route validation against the running `ai-service`

## Result Summary

### Passed

- `GET /game/sessions` recovers after service restart and returns `200`
- real HTTP flow `create -> turn -> archive -> create -> recall` passes end-to-end
- turn responses now return separate `primaryDialogue` and `primaryNarration`
- turn payload `result.turns` now contains:
  - player speech
  - character narration
  - character speech
- archive promotion still works after the reply-shape refactor
- recall flow still selects long-memory items
- browser smoke can:
  - load the app without the red `unexpected game service error` banner
  - open a real session
  - submit a turn from the UI
  - render both narration and speech bubbles in the dialogue stage

### Not fully passed

- browser automation did not complete the right-drawer / relation-panel assertion
- browser automation did not complete the session-rail archive-button assertion

These two are currently blocked by drawer/overlay interaction behavior in automation, not by the backend route layer.

## Evidence

### HTTP route flow

Statuses:

- `POST /game/sessions` -> `200`
- `POST /game/sessions/{id}/turns` -> `200`
- `PATCH /game/sessions/{id}` archive -> `200`
- second `POST /game/sessions` -> `200`
- second `POST /game/sessions/{id}/turns` recall -> `200`

Observed response shape on first turn:

- `primaryDialogue`: `嗯。`
- `primaryNarration`: `指尖无意识地摩挲着借书卡边缘，垂眸片刻，耳尖微微泛起一点淡色，随即抬眼望向窗外连绵的雨帘，睫毛轻轻颤了一下。`
- `result.turns` shape:
  - player `speech`
  - character `narration`
  - character `speech`

Archive result:

- `archivePromotion.promotedCount = 2`
- `archivePromotion.profileCount = 1`

Recall result:

- `longMemory.selectedItems` count: `2`
- recall reply still produced separated fields:
  - `primaryDialogue`: `你记得啊。`
  - `primaryNarration`: `她指尖轻轻抚过借书卡边缘，垂眸片刻，耳尖微不可察地泛起一点淡色。窗外雨声渐密，她抬眼望向你，目光安静，像在确认一句久违的诺言是否真的落了地。`

### Browser smoke

Smoke session title:

- `ui-smoke-1774699080`

Browser assertions that passed:

- page load succeeds
- no red `unexpected game service error` banner on load
- target session can be opened
- a new turn can be sent from the UI
- narration bubble becomes visible
- speech bubble becomes visible

Browser assertions that did not complete:

- relation drawer visible
- long-memory panel visible
- archive action through the session rail

Notes:

- the Playwright run repeatedly hit drawer/scrim interception while trying to drive side-panel interactions
- this means the core conversation flow is working, but the side-drawer interaction model is still brittle under automation

## Artifacts

- browser summary JSON: `/tmp/rag-full-chain-browser.json`
- browser screenshot: `/tmp/rag-full-chain-browser.png`

## Conclusion

The runtime error shown in the screenshot is not reproducing after restart, and the conversation stack itself is working:

- no visible director dependency in the core turn path
- dialogue/narration split is live
- long-memory archive/recall still works

The remaining instability is concentrated in UI drawer interactions, especially automated access to:

- session-rail archive action
- relation/long-memory drawer visibility

## Recommended next step

Add stable test hooks for drawer state and panel actions, for example:

- `data-testid` on left/right drawer toggles
- `data-testid` on session-row primary/open and archive buttons
- `data-testid` on relation drawer root and long-memory section

That would make the browser e2e layer reliable enough to promote this from smoke coverage to full UI regression coverage.
