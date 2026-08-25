---
applyTo: "docs/TC-*/pr-description.md"
---

# Instructions — Phase 8: Pull Request Creation

## Role
You are creating the final deliverable of the agentic SDLC cycle. The PR description must be self-contained — a reviewer unfamiliar with this project should be able to understand what was built and how to review it.

## ALL 5 Sections Are Mandatory

### Section 1: Summary
- Exactly 2-3 sentences
- Cover: what was built, why (the user story), and that it was driven by agentic SDLC
- Written for a technical manager or reviewer who hasn't followed the project

### Section 2: Changes Made
Four tables:
1. **SDLC Artifacts** — `docs/{TC_ID}/*.md` files (requirements, architecture, etc.)
2. **Source Code** — `src/docsync/*.py` files with specific reason per file
3. **Infrastructure & Config** — workflow, instructions, prompts, config
4. **Tests** — `tests/*.py` files with what each covers

Every modified file must appear in exactly one table.

### Section 3: Test Evidence
- Copy test session output from `docs/{TC_ID}/verification.md` VERBATIM
- Include the platform line, test collection count, and final summary
- Include the coverage table
- If CI results are available, link to them

### Section 4: Known Limitations
- Be honest — do not hide deferred work
- Every item from code-review.md with status PARTIAL counts as a limitation
- Every design review GAP marked DEFERRED goes here
- Format: what the limitation is, and why it was deferred (v2, out of scope, etc.)

### Section 5: Reviewer Checklist
The checklist must be actionable (a reviewer can verify each item):
- "Check that `find_page` in `confluence_client.py` searches by `docsync:source_path` property"
- NOT "Verify idempotency is correct" (too vague)

Include checks for:
- Each FR (FR-01..FR-12): where to find the implementation
- NFR-01 security: where to verify no secrets
- NFR-03 retry: which decorator and on which methods
- NFR-07 idempotency: which property and which method
- Test pass: exact command to run
- Dry-run: exact command to run
- Architecture alignment: which files to compare
- Design decisions: which DD and where implemented

## CHANGELOG.md Format
```markdown
## [1.0.0] - {TODAY}

### Added
- DocSync CLI tool (`docsync sync`) for automated GitHub → Confluence sync
- {List each major feature}

### Architecture
- {Key architectural decisions}

### Known Limitations (v1)
- {List deferred items}
```

## Prohibited Behaviors
- Do NOT fabricate test output — use actual output from docs/{TC_ID}/verification.md
- Do NOT omit any of the 5 sections
- Do NOT write vague reviewer checklist items
- Do NOT hide known limitations
- Do NOT list files that don't exist
