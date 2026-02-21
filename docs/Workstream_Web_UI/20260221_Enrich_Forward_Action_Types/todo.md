# Task: Enrich Forward Action Types and Fix Localization

## Objectives
1.  **Frontend**: Enrich action types in forwarding records (`History` page).
    - Map `forwarded`/`success` to `已转发`.
    - Map `error` to `失败`.
    - Map `filtered` to `已过滤`.
    - Enhance Badge colors.
2.  **Frontend**: Localize `message_type` to Chinese.
3.  **Frontend**: Fix `processing_time` display bug (show `-` only if null/undefined, not for `0`).
4.  **Backend**: Add `duration` to `FORWARD_FILTERED` event.
5.  **Backend**: Ensure `msg_text` and `msg_type` are correctly captured for all events.

## Todo List
- [x] Backend: Update `FilterMiddleware` to include `duration` in `FORWARD_FILTERED`.
- [x] Backend: Update `Container._on_forward_filtered` to pass `duration` to `stats_repo`.
- [x] Frontend: Create Chinese mapping for `message_type`.
- [x] Frontend: Update `History.tsx` status display logic and labels.
- [x] Frontend: Fix `processing_time` conditional rendering.
- [x] Verification: Check the web panel `History` page.
