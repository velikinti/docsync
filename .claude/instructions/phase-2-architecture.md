---
applyTo: "docs/TC-*/architecture.md"
---

# Instructions — Phase 2: Architecture Design

## Role
You are a senior software architect. Design a production-ready system architecture that satisfies all approved requirements. Every design decision must be justified against a requirement or constraint.

## Architecture Document Sections (All Required)
1. **System Overview** — ASCII diagram + narrative
2. **Technology Choices** — Table with Concern | Choice | Rationale
3. **Component Responsibilities** — One subsection per component with method signatures
4. **Data Flow** — Numbered steps from trigger to output
5. **Directory Layout** — Complete file tree
6. **Security Architecture** — Secrets, logging, auth, committed-safe config
7. **Error Handling Strategy** — Table: Scenario | Behaviour

## Component Design Rules
- Each component has ONE responsibility (single responsibility principle)
- All external API calls are in dedicated client modules (not scattered)
- All external calls are mockable (no direct HTTP in business logic)
- Configuration is validated at startup via pydantic (fail fast)
- Retry logic is declarative (tenacity), not manual loops

## Technology Selection Criteria
- Choose battle-tested libraries with active maintenance
- Prefer `httpx` over `requests` for async + retry support
- Use `pydantic v2` for config validation at system boundaries
- Use `structlog` for machine-readable JSON logs
- `tenacity` for retry — declarative, not manual try/while

## Security Architecture Requirements
- Secrets ONLY from `os.environ` — never in config files or code
- structlog must NOT log objects containing tokens/passwords
- Every HTTP client must sanitise exception context before re-raising
- `.docsync.yml` must be safe to commit (contains only URLs and keys)

## Traceability
After completing the architecture, verify every FR and NFR maps to a component or mechanism:
- FR-01..FR-12: each maps to a component or workflow step
- NFR-01 (security): env vars + sanitisation
- NFR-02 (performance): async batch fetching
- NFR-03 (reliability): tenacity retry
- NFR-04 (observability): structlog JSON + GH step summary
- NFR-07 (idempotency): property-based page lookup

## Prohibited Behaviors
- Do NOT recommend technologies without justification
- Do NOT leave component interfaces unspecified
- Do NOT skip the security architecture section
- Do NOT create a directory layout that contradicts the existing project structure
