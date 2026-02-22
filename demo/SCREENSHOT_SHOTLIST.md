# Screenshot Shot List (ChatGPT UI)

Capture these in order and keep timestamps visible where possible.

## A) Prove App Is Connected

1. `01-app-connected.png`
   - ChatGPT UI showing the connected RetailOps MCP app/integration enabled.
   - Include the app name and connection status in the same frame.

2. `02-tools-visible.png`
   - Chat/session UI where available tools are visible.
   - Must show at least: `search`, `fetch`, `inventory_lookup`, `reserve_item`, `create_transfer`, `create_ticket`.

## B) Prove Read Tool Calls Are Happening

3. `03-search-tool-call.png`
   - Prompt asking a policy question.
   - Tool activity panel showing `search(...)` invocation and returned doc ids/URLs.

4. `04-fetch-tool-call.png`
   - Tool activity panel showing `fetch(id=...)` call.
   - Include returned citation URL and excerpt in-frame.

5. `05-grounded-answer-with-citation.png`
   - Final assistant answer that cites internal docs.
   - Citation link/footnote visible.

## C) Prove Action Tool Calls + Confirmation

6. `06-inventory-lookup-call.png`
   - User asks for hero SKU availability.
   - Tool activity shows `inventory_lookup(...)` with nearby store results.

7. `07-reserve-preview-confirmation-required.png`
   - Tool activity/output showing reserve preview (`status: preview` or confirm required).
   - Confirm token or explicit confirmation prompt visible.

8. `08-reserve-confirmed-write.png`
   - Follow-up with confirmation.
   - Tool activity/output shows successful reserve write (`status: reserved`).

9. `09-transfer-preview-confirmation-required.png`
   - Merch flow showing `create_transfer(...)` preview requiring confirmation.

10. `10-transfer-confirmed-write.png`
   - Confirmed transfer result (`status: created`, transfer id visible).

11. `11-ticket-created-write.png`
   - Support flow showing `create_ticket(...)` success with `ticket_id`.

## D) Prove Auditability / End-to-End Flow

12. `12-end-to-end-summary.png`
   - A single summary response or tool trace showing all major actions executed in one session.
   - Must include at least reserve + transfer + ticket outcomes.

## Optional High-Confidence Extras

13. `13-role-denied-transfer.png`
   - Attempt transfer with non-merch role and show denial/guardrail.

14. `14-health-check-or-deployment-proof.png`
   - Browser tab with deployed MCP `/health` endpoint returning `ok` over HTTPS.
