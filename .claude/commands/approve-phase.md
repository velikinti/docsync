---
description: "Approve or reject an SDLC phase for a test case. Usage: /approve-phase TC-XXX N [APPROVED|REJECTED] [reason]"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
---

# DocSync — Approve Phase

## Inputs
$ARGUMENTS format: `TC-XXX N [APPROVED|REJECTED] [reason text]`

Examples:
- `/approve-phase TC-003 1 APPROVED`
- `/approve-phase TC-003 2 REJECTED "Missing async error handling"`

Parse:
- `TEST_CASE` — first token (e.g. `TC-003`)
- `PHASE_N` — second token (1–8)
- `DECISION` — third token (`APPROVED` or `REJECTED`), default `APPROVED`
- `REASON` — remaining text (required if REJECTED)

## What This Does

1. Read `outputs/${TEST_CASE}/phase-status.json`
2. Verify phase `${PHASE_N}` has `status: "PENDING_APPROVAL"` — if not, report current status
3. Update the phase entry:
   ```json
   {
     "status": "<DECISION>",
     "decision": "<DECISION>",
     "decided_at": "<ISO timestamp>",
     "reason": "<REASON or null>"
   }
   ```
4. Write the updated JSON back to `outputs/${TEST_CASE}/phase-status.json`
5. Write `outputs/${TEST_CASE}/phase-N-<name>/approval.json`:
   ```json
   {
     "phase": <N>,
     "test_case": "${TEST_CASE}",
     "decision": "<DECISION>",
     "decided_at": "<ISO timestamp>",
     "reason": "<REASON or null>"
   }
   ```
6. Report the result:
   - If APPROVED: "Phase N approved. Ready to run `/phase-N-name TC-XXX`"
   - If REJECTED: "Phase N rejected. Reason: <reason>. Re-run `/phase-N-name TC-XXX` after addressing the feedback."

## Phase Name Map
| N | Name | Next Slash Command |
|---|------|--------------------|
| 1 | Requirements | `/architecture ${TC}` |
| 2 | Architecture | `/design-review ${TC}` |
| 3 | Design Review | `/impl-planning ${TC}` |
| 4 | Impl Planning | `/implementation ${TC}` |
| 5 | Implementation | `/code-review ${TC}` |
| 6 | Code Review | `/verification ${TC}` |
| 7 | Verification | `/pr ${TC}` |
| 8 | PR Creation | pipeline complete |

> **Note:** You can also approve phases using the PowerShell script directly:
> ```powershell
> scripts\approve-phase.ps1 -Phase N -Decision APPROVED -TestCase TC-XXX
> ```
