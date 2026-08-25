# DocSync — Agentic SDLC Pipeline

## Project
**DocSync** is a Python CLI tool that automatically syncs Markdown files from GitHub repositories
to Confluence Cloud whenever code is pushed to `main`. Built using an 8-phase Agentic SDLC
pipeline driven entirely by **Claude Code**.

- Source code: `src/docsync/`
- Tests: `tests/`
- SDLC artifacts: `docs/TC-XXX/`
- Phase outputs: `outputs/TC-XXX/`
- Pipeline status: `outputs/TC-XXX/phase-status.json`

## Tech Stack
Python 3.10+ · click · httpx (async) · pydantic v2 · tenacity · structlog · markdown2 · lxml · GitHub Actions · Confluence Cloud REST API v2

## Development Commands
```powershell
# Install in dev mode
pip install -e ".[dev]"

# Run tests
pytest tests/ -v --tb=short

# Run with coverage
pytest tests/ --cov=src/docsync --cov-report=term-missing

# Dry-run sync (no writes to Confluence)
docsync sync --dry-run --config .docsync.yml
```

---

## Slash Commands (Phase Runners)

Each SDLC phase has a dedicated slash command in `.claude/commands/`. Run them in Claude Code chat.

| Phase | Name | Slash Command | Output |
|-------|------|---------------|--------|
| 1 | Requirements | `/requirements [TC-ID]` | `docs/${TC}/requirements.md` |
| 2 | Architecture | `/architecture [TC-ID]` | `docs/${TC}/architecture.md` |
| 3 | Design Review | `/design-review [TC-ID]` | `docs/${TC}/design-review.md` |
| 4 | Impl Planning | `/impl-planning [TC-ID]` | `docs/${TC}/impl-plan.md` |
| 5 | Implementation | `/implementation [TC-ID]` | `src/docsync/` |
| 6 | Code Review | `/code-review [TC-ID]` | `docs/${TC}/code-review.md` |
| 7 | Verification | `/verification [TC-ID]` | `docs/${TC}/verification.md` |
| 8 | PR Creation | `/pr [TC-ID]` | `docs/${TC}/pr-description.md` |

### Additional Commands
| Command | Purpose |
|---------|---------|
| `/pipeline [TC-ID] "[USER-STORY]"` | Run the full 8-phase pipeline end-to-end |
| `/approve-phase [TC-ID] [N]` | Approve phase N for a test case |
| `/tc-report` | Generate a status report for all test cases |

### How to Run a Single Phase
1. Initialize the pipeline first (if new TC):
   ```powershell
   scripts\init-pipeline.ps1 -TestCase TC-XXX -UserStory "US-XXX: ..."
   ```
2. Run the phase slash command in Claude Code:
   ```
   /requirements TC-XXX
   ```
3. Claude runs the phase, writes outputs, and presents a **Human Checkpoint** summary.
4. Approve or reject:
   ```powershell
   scripts\approve-phase.ps1 -Phase 1 -Decision APPROVED -TestCase TC-XXX
   # or
   scripts\approve-phase.ps1 -Phase 1 -Decision REJECTED -Reason "..." -TestCase TC-XXX
   ```
5. Proceed to the next phase.

### How to Run the Full Pipeline (Autonomous)
```
/pipeline TC-XXX "US-XXX: As a developer, I want..."
```

Or step-by-step with approvals between each phase:
```
/requirements TC-XXX  → approve →
/architecture TC-XXX  → approve →
/design-review TC-XXX → approve →
/impl-planning TC-XXX → approve →
/implementation TC-XXX → approve →
/code-review TC-XXX   → approve →
/verification TC-XXX  → approve →
/pr TC-XXX            → approve
```

---

## Claude Code Construct Layout

Mirrors the GitHub Copilot folder structure — three separate folders for each construct type:

```
.claude/
├── instructions/                    # Role context & coding rules (≡ .github/instructions/)
│   ├── docsync.md                   #   Applies to src/docsync/**
│   ├── phase-1-requirements.md      #   Requirements analyst role
│   ├── phase-2-architecture.md      #   Architect role
│   ├── phase-3-design-review.md     #   Reviewer role
│   ├── phase-4-impl-planning.md     #   Tech lead role
│   ├── phase-5-implementation.md    #   Developer role
│   ├── phase-6-code-review.md       #   Peer reviewer role
│   ├── phase-7-verification.md      #   QA engineer role
│   └── phase-8-pr.md               #   PR author role
│
├── agents/                          # Claude Code agents (≡ .github/prompts/ orchestrator)
│   └── orchestration-agent.md       #   Drives the full 8-phase pipeline
│
├── skills/                          # Skill agents (≡ .github/skills/)
│   ├── confluence-publisher/
│   │   └── SKILL.md                 #   Publish SDLC docs to Confluence
│   ├── github-pr-creator/
│   │   └── SKILL.md                 #   Create GitHub Pull Requests
│   └── tc-report-generator/
│       └── SKILL.md                 #   Generate HTML/Markdown/JSON pipeline reports
│
└── commands/                        # Slash commands (≡ .github/prompts/ phase prompts)
    ├── requirements.md              #   /requirements [TC-ID]
    ├── architecture.md              #   /architecture [TC-ID]
    ├── design-review.md             #   /design-review [TC-ID]
    ├── impl-planning.md             #   /impl-planning [TC-ID]
    ├── implementation.md            #   /implementation [TC-ID]
    ├── code-review.md               #   /code-review [TC-ID]
    ├── verification.md              #   /verification [TC-ID]
    ├── pr.md                        #   /pr [TC-ID]
    ├── pipeline.md                  #   /pipeline [TC-ID] "USER-STORY"
    ├── approve-phase.md             #   /approve-phase TC-XXX N [APPROVED|REJECTED]
    └── tc-report.md                 #   /tc-report [TC-XXX] [html|markdown|json]
```

## Agents & Skills

| Type | Name | Location | Purpose |
|------|------|----------|---------|
| Agent | `orchestration-agent` | `.claude/agents/orchestration-agent.md` | Drive the full 8-phase pipeline autonomously |
| Skill | `confluence-publisher` | `.claude/skills/confluence-publisher/SKILL.md` | Publish SDLC phase docs to Confluence |
| Skill | `github-pr-creator` | `.claude/skills/github-pr-creator/SKILL.md` | Create GitHub Pull Requests via gh CLI |
| Skill | `tc-report-generator` | `.claude/skills/tc-report-generator/SKILL.md` | Generate HTML/Markdown/JSON pipeline reports |

---

## Human-in-the-Loop Checkpoints

**EVERY phase requires explicit human approval before proceeding to the next.**

Each slash command automatically:
1. Checks the previous phase is `APPROVED` in `outputs/TC-XXX/phase-status.json` (pre-flight)
2. Writes output to `docs/TC-XXX/[phase-doc].md`
3. Archives output to `outputs/TC-XXX/phase-N-name/output.md`
4. Writes `outputs/TC-XXX/phase-N-name/agent-log.json`
5. Updates `outputs/TC-XXX/phase-status.json` → phase N = `PENDING_APPROVAL`
6. Presents a checkpoint summary with the exact approval command to run

**Approval commands:**
```powershell
scripts\approve-phase.ps1 -Phase N -Decision APPROVED -TestCase TC-XXX
scripts\approve-phase.ps1 -Phase N -Decision REJECTED -Reason "..." -TestCase TC-XXX
```

---

## Pipeline Status Tracking

```powershell
# Initialize a new test case
scripts\init-pipeline.ps1 -TestCase TC-XXX -UserStory "US-XXX: ..."

# Check status of all phases for a TC
scripts\check-agent-status.ps1 -TestCase TC-XXX

# Check if a specific phase is approved
scripts\check-agent-status.ps1 -Prereq 2 -TestCase TC-XXX

# View a phase output
cat outputs\TC-XXX\phase-3-design-review\output.md

# Resume a pipeline from a specific phase (after interruption)
scripts\resume-pipeline.ps1 -TestCase TC-XXX -FromPhase 3
```

---

## Output Directory Structure

```
outputs/
├── phase-status.json              # Master tracker — lists all TC-XXX runs
└── TC-XXX/
    ├── phase-status.json          # Status of all 8 phases for this TC
    ├── phase-1-requirements/
    │   ├── output.md
    │   ├── agent-log.json
    │   └── approval.json
    ├── phase-2-architecture/
    ├── phase-3-design-review/
    ├── phase-4-impl-planning/
    ├── phase-5-implementation/
    ├── phase-6-code-review/
    ├── phase-7-verification/
    └── phase-8-pr/
```

---

## Security Rules (Always Enforce)
- NEVER hardcode `CONFLUENCE_API_TOKEN`, `CONFLUENCE_USER`, or `GITHUB_TOKEN` in any file
- All secrets come from `os.environ` only
- `structlog` must NOT log objects containing tokens/passwords
- No secrets in `.docsync.yml`, logs, or commit history

## Code Conventions
- Python 3.10+, `from __future__ import annotations` in every module
- Type-annotated throughout; use dataclasses for return values
- No `print()` in library code — use `structlog`
- Raise `RuntimeError` from HTTP clients; `FileNotFoundError` for GitHub 404
- All Confluence mutating calls use `tenacity` retry (3×, exponential back-off)
- `find_page` searches by `docsync:source_path` property, NOT title

## Key Design Decisions
- **DD-01**: Page identity = `docsync:source_path` property — prevents title collisions
- **DD-02**: Async httpx + `asyncio.Semaphore(batch_size)` for GitHub file fetching
- **DD-03**: XHTML validation with lxml; fallback to code-block macro if invalid
- **DD-04**: Archive = Confluence trash (DELETE endpoint) — recoverable
- **DD-05**: Sanitise HTTP exceptions before logging — prevents secret leakage
