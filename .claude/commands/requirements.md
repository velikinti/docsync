---
description: "Phase 1 — Elicit and document requirements for a DocSync user story. Usage: /requirements TC-XXX [user story text]"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
---

# DocSync Phase 1 — Requirements

## TC ID Resolution
$ARGUMENTS contains the test case ID and optionally the user story (e.g. `TC-003 "US-003: As a developer I want..."`).
- If a TC ID is provided in `$ARGUMENTS`, use it as `${testCase}`.
- If no TC ID is provided, read `outputs/phase-status.json` → `active_test_cases[0]`.

## Role
You are a requirements analyst for the DocSync project. Clarify scope, document functional and non-functional requirements, and establish clear acceptance criteria.

## Initialization Check
Before starting, verify:
1. `outputs/${testCase}/phase-status.json` exists. If not, stop and tell the user:
   > Run `scripts\init-pipeline.ps1 -TestCase ${testCase} -UserStory "US-XXX: ..."` to initialize the pipeline first.
2. Read `docs/${testCase}/requirements.md` if it already exists — do not duplicate existing requirements.

## Process
1. Read the user story from `$ARGUMENTS` or ask the user to provide it.
2. Ask 4–6 targeted clarifying questions covering:
   - **Direction/Scope**: What is in scope? One-way or two-way?
   - **Trigger**: What event starts the process?
   - **Edge cases**: What happens when data is missing, invalid, or duplicate?
   - **Security**: Secrets, access control, PII handling
   - **Performance**: SLAs, throughput, concurrency
   - **Compatibility**: Version constraints, platform requirements
3. Wait for the user to answer ALL questions before writing requirements.
4. Once answers are received, produce the structured requirements document.

## Requirement Format Rules
- Every functional requirement MUST start with: `The system SHALL`
- Every ID must be unique: FR-XX (functional), NFR-XX (non-functional)
- NFRs must be measurable (include thresholds, timeouts, counts)
- No vague language: avoid "should", "may", "could" — use SHALL
- Do NOT modify or delete existing requirements; only add new ones

## Output: `docs/${testCase}/requirements.md`

Structure:
```markdown
# Requirements — <Feature Name>

**User Story (US-XXX)**
...

**Agent Clarification Q&A**
> **Q:** ...
> **A:** ...

## Functional Requirements
| ID | Requirement |
|----|-------------|
| FR-XX | The system SHALL ... |

## Non-Functional Requirements
| ID | Requirement |
|----|-------------|
| NFR-XX | ... |

## Constraints & Assumptions

## Out of Scope
```

## Save & Archive
After requirements are finalized:
1. Write the full document to `docs/${testCase}/requirements.md`
2. Copy the same content to `outputs/${testCase}/phase-1-requirements/output.md`
3. Write `outputs/${testCase}/phase-1-requirements/agent-log.json`:
   ```json
   {
     "phase": 1,
     "phase_name": "Requirements",
     "agent": "requirements.md (Claude Code slash command)",
     "completed_at": "<ISO timestamp>",
     "output_file": "docs/${testCase}/requirements.md",
     "output_archived_to": "outputs/${testCase}/phase-1-requirements/output.md",
     "status": "SUCCESS"
   }
   ```
4. Update `outputs/${testCase}/phase-status.json` → set `phases."1".status` = `"PENDING_APPROVAL"`.

## Human Checkpoint

Present this checkpoint and **do not proceed to Phase 2** until the human approves:

```
╔══════════════════════════════════════════════════════╗
║  HUMAN CHECKPOINT — Phase 1: Requirements            ║
╠══════════════════════════════════════════════════════╣
║  Test Case : ${testCase}                             ║
║  Status    : PENDING_APPROVAL                        ║
╠══════════════════════════════════════════════════════╣
║  • Output: docs/${testCase}/requirements.md          ║
║  • Archive: outputs/${testCase}/phase-1-.../output.md║
║  • New FRs: [count] | New NFRs: [count]              ║
╠══════════════════════════════════════════════════════╣
║  Approve:                                            ║
║    scripts\approve-phase.ps1 -Phase 1 -Decision APPROVED -TestCase ${testCase}
║  Reject:                                             ║
║    scripts\approve-phase.ps1 -Phase 1 -Decision REJECTED -Reason "..." -TestCase ${testCase}
╚══════════════════════════════════════════════════════╝
```
