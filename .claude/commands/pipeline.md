---
description: "Run the DocSync SDLC pipeline with human checkpoints. Supports full run, resume, and phase ranges. Usage: /pipeline TC-XXX [\"US-XXX: story\"] [--from N] [--to N]"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
---

# DocSync — Full Pipeline Orchestration

## Inputs
$ARGUMENTS contains the test case ID and optional flags:
```
TC-XXX "US-XXX: As a developer, I want..."
TC-XXX --from 4 --to 6
TC-XXX "US-XXX: ..." --from 2 --to 5
```

Parse from $ARGUMENTS in this order:
- `TEST_CASE` — first non-flag token (e.g. `TC-003`)
- `USER_STORY` — quoted string not starting with `--` (optional if TC already initialised)
- `--from N` — first phase to run (integer 1–8, default: first non-APPROVED phase)
- `--to N` — last phase to run inclusive (integer 1–8, default: 8)

If no TEST_CASE, read `outputs/phase-status.json` → `active_test_cases[0]`.

### Range Validation
After parsing, validate:
- `FROM` and `TO` are integers between 1 and 8
- `FROM` ≤ `TO`
- If either is out of range, stop immediately with:
  > **Error:** `--from` and `--to` must be integers between 1 and 8, and `--from` must be ≤ `--to`.

## Role
You are the **DocSync SDLC Orchestration Agent**. Drive the full 8-phase pipeline for `TEST_CASE` end-to-end, with human checkpoints between each phase.

## Pre-Pipeline Setup
1. Check if `outputs/${TEST_CASE}/phase-status.json` exists.
   - If not, run: `scripts\init-pipeline.ps1 -TestCase ${TEST_CASE} -UserStory "${USER_STORY}"`
2. Read `outputs/${TEST_CASE}/phase-status.json` to determine which phases are already `APPROVED`.
3. Resolve the effective range:
   - `FROM` = `--from` value if supplied, otherwise the first non-APPROVED phase in the full pipeline
   - `TO`   = `--to` value if supplied, otherwise `8`
4. If `--from` was NOT supplied and all phases up to `TO` are already APPROVED, report and exit:
   > All phases 1–TO are already APPROVED. Nothing to run.

## Phase Execution Rules

### Pre-flight for each phase
Before executing phase N (even when using `--from`), verify phase N-1 has status `APPROVED` in `outputs/${TEST_CASE}/phase-status.json` (Phase 1 has no prerequisite).

If the pre-flight fails on phase `FROM`, stop immediately:
> **Blocked:** Phase FROM cannot run — Phase FROM-1 is not APPROVED.
> Approve it first: `scripts\approve-phase.ps1 -Phase FROM-1 -Decision APPROVED -TestCase TEST_CASE`

### Phase Loop (Phases FROM–TO)

For each phase N from `FROM` to `TO` in order:

1. **Execute** the phase logic (same logic as the corresponding `/phase-name` slash command)
2. **Write** outputs:
   - `docs/${TEST_CASE}/<phase-doc>.md`
   - `outputs/${TEST_CASE}/phase-N-<name>/output.md`
   - `outputs/${TEST_CASE}/phase-N-<name>/agent-log.json`
3. **Update** `outputs/${TEST_CASE}/phase-status.json` → phase N = `PENDING_APPROVAL`
4. **Present** the Human Checkpoint and **STOP** — wait for explicit approval before proceeding
5. After phase N is approved, if N = `TO` → present the Range Complete summary and **exit** (do not continue to phase TO+1)

### Phase Reference
| Phase | Name | Output Doc |
|-------|------|-----------|
| 1 | Requirements | `docs/${TC}/requirements.md` |
| 2 | Architecture | `docs/${TC}/architecture.md` |
| 3 | Design Review | `docs/${TC}/design-review.md` |
| 4 | Impl Planning | `docs/${TC}/impl-plan.md` |
| 5 | Implementation | `src/docsync/` (multiple files) |
| 6 | Code Review | `docs/${TC}/code-review.md` |
| 7 | Verification | `docs/${TC}/verification.md` |
| 8 | PR Creation | `docs/${TC}/pr-description.md` |

## Resuming After an Interruption

If the pipeline was interrupted (e.g. stopped at Phase 3):

1. Read `outputs/${TEST_CASE}/phase-status.json` to confirm which phases are `APPROVED`.
2. Announce what will be skipped:
   ```
   Resuming ${TEST_CASE} from Phase N (<Phase Name>).
   Phases 1–<N-1> are already APPROVED — skipping.
   ```
3. Proceed directly to executing phase N.

**Key rule**: Never re-run a phase that is already `APPROVED` unless the user explicitly asks to redo it.

### Range + Resume interaction
- `/pipeline TC-XXX --from 4 --to 6` with phase 4 already APPROVED → starts at phase 5 (first non-APPROVED phase within the range), announces "Phase 4 already APPROVED — skipping."
- `/pipeline TC-XXX --from 4 --to 6` with all of 4–6 APPROVED → reports "Phases 4–6 already APPROVED. Nothing to run."
- `--from` **forces** a specific start regardless of prior approval only when combined with an explicit "redo" intent — otherwise it still skips already-APPROVED phases within the range.

## Human Checkpoint Format

```
╔══════════════════════════════════════════════════════╗
║  HUMAN CHECKPOINT — Phase N: <Name>                  ║
╠══════════════════════════════════════════════════════╣
║  Test Case : TEST_CASE                               ║
║  Running   : Phases FROM–TO   (omit if FROM=1, TO=8) ║
║  Status    : PENDING_APPROVAL                        ║
╠══════════════════════════════════════════════════════╣
║  Key outputs (bullet summary, max 5 items)           ║
╠══════════════════════════════════════════════════════╣
║  Approve:                                            ║
║    scripts\approve-phase.ps1 -Phase N -Decision APPROVED -TestCase TEST_CASE
║  Reject:                                             ║
║    scripts\approve-phase.ps1 -Phase N -Decision REJECTED -Reason "..." -TestCase TEST_CASE
╚══════════════════════════════════════════════════════╝
```

**DO NOT proceed to the next phase until the user runs the approval command.**
**When N = TO: after approval, present the Range Complete summary below instead of continuing.**

## Post-Pipeline Actions (after Phase 8 is APPROVED)

After all 8 phases are approved, offer:

1. **Publish to Confluence**: "Use the `confluence-publisher` agent for `${TEST_CASE}`"
2. **Create GitHub PR**: "Use the `github-pr-creator` agent for `${TEST_CASE}`"
3. **Generate report**: `/tc-report`

## Summaries

### Full Pipeline Complete (TO = 8)
```
╔══════════════════════════════════════════════════════╗
║  PIPELINE COMPLETE — TEST_CASE                       ║
╠══════════════════════════════════════════════════════╣
║  Phases completed : 8/8                              ║
║  All outputs in   : outputs/TEST_CASE/               ║
║  SDLC docs in     : docs/TEST_CASE/                  ║
╚══════════════════════════════════════════════════════╝
```

### Range Complete (TO < 8)
```
╔══════════════════════════════════════════════════════╗
║  RANGE COMPLETE — TEST_CASE                          ║
╠══════════════════════════════════════════════════════╣
║  Phases run      : FROM–TO                           ║
║  All APPROVED    : YES                               ║
║  Remaining phases: TO+1–8 (not yet run)              ║
╠══════════════════════════════════════════════════════╣
║  To continue from phase TO+1:                        ║
║    /pipeline TEST_CASE --from TO+1                   ║
║  To run a different range:                           ║
║    /pipeline TEST_CASE --from X --to Y               ║
║  To run the full remaining pipeline:                 ║
║    /pipeline TEST_CASE                               ║
╚══════════════════════════════════════════════════════╝
```
