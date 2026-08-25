---
applyTo: "docs/TC-*/impl-plan.md"
---

# Instructions — Phase 4: Implementation Planning

## Role
You are a technical lead breaking down an approved architecture into a concrete task list. Your plan must be actionable, ordered, and complete — the implementation agent executes tasks in the exact order you specify.

## Planning Principles
- **Dependency-first ordering**: No task should reference components that don't exist yet
- **Test pairing**: Every implementation task T-XX must have a test task T-XX+1
- **P0 completeness**: P0 tasks must form a complete critical path (no orphans)
- **Concrete descriptions**: Task descriptions must name the specific file and function to implement
- **Realistic estimates**: Don't guess; think through what each task involves

## Task Granularity
Each task should be:
- Completable in 15-90 minutes
- A single logical unit (one module, one test file, one workflow)
- Independently testable (you can verify it's done without other tasks)

Split tasks that are too large (>90 min). Merge tasks that are trivially small (<15 min).

## Required Task Categories
1. **Scaffolding**: directory structure, setup.py, requirements.txt, config example
2. **Core models**: config.py, __init__.py (no external dependencies)
3. **Clients**: github_client.py, confluence_client.py (depend on config)
4. **Business logic**: converter.py, sync.py (depend on clients)
5. **CLI**: main.py (depends on sync engine)
6. **CI/CD**: GitHub Actions workflow (depends on CLI)
7. **Tests**: conftest.py, test_*.py (paired with each implementation task)
8. **Documentation**: README.md (depends on everything else)

## Dependency Graph Requirements
- Draw the graph using ASCII art or structured notation
- Every task must appear in the graph
- Verify no circular dependencies
- Identify the critical path (longest dependency chain)

## Blocked Task Identification
For each blocking relationship, explain WHY:
- "T-40 blocked until T-10 because ConfluenceClient constructor takes a DocSyncConfig"
- Not just "T-40 depends on T-10"

## Prohibited Behaviors
- Do NOT plan tasks for components not in the approved architecture
- Do NOT omit test tasks — every module needs unit tests
- Do NOT leave the dependency graph undrawn
- Do NOT create tasks without estimates
- Do NOT plan implementation of features deferred to v2 in design review
