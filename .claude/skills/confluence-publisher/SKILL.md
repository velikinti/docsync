# DocSync — Confluence Publisher Skill

## Purpose
Publish DocSync SDLC phase documents to Confluence Cloud using the Atlassian MCP tool or REST API.

## When to Use
- After all 8 SDLC phases are approved for a test case
- When the user says "publish to Confluence", "create Confluence pages", or "sync docs to Confluence"
- When the orchestration agent reaches post-pipeline Action 1

---

## Instructions

### Step 1 — Load Phase Documents
For the given `TEST_CASE`, read the following files:

| Phase | File |
|-------|------|
| Requirements     | `docs/${TEST_CASE}/requirements.md` |
| Architecture     | `docs/${TEST_CASE}/architecture.md` |
| Design Review    | `docs/${TEST_CASE}/design-review.md` |
| Impl Plan        | `docs/${TEST_CASE}/impl-plan.md` |
| Code Review      | `docs/${TEST_CASE}/code-review.md` |
| Verification     | `docs/${TEST_CASE}/verification.md` |
| PR Description   | `docs/${TEST_CASE}/pr-description.md` |

### Step 2 — Check for Existing Pages
Use `mcp_atlassian_mcp_confluence_search` to search for each page title in the target space:

```
title = "DocSync SDLC — <TEST_CASE> — <Phase Name>" AND space.key = "<SPACE_KEY>"
```

### Step 3 — Create or Update Pages
- **Not found** → `mcp_atlassian_mcp_confluence_create_page`
- **Found** → `mcp_atlassian_mcp_confluence_update_page`

Use the following page hierarchy:
```
Parent: "DocSync SDLC — <TEST_CASE>"
  └── Requirements
  └── Architecture
  └── Design Review
  └── Implementation Plan
  └── Code Review
  └── Verification
  └── PR Description
```

First create the parent page, then create each child page under it.

### Step 4 — Page Body Format
Convert Markdown content to Confluence storage format:
- `# Heading` → `<h1>Heading</h1>`
- `**bold**` → `<strong>bold</strong>`
- `` `code` `` → `<code>code</code>`
- ` ```block``` ` → `<ac:structured-macro ac:name="code"><ac:plain-text-body>...</ac:plain-text-body></ac:structured-macro>`
- Bullet lists → `<ul><li>...</li></ul>`

For simple content, use the `wiki` representation with `wiki` as contentRepresentation parameter.

### Step 5 — Report
After all pages are created/updated, report:
```
Confluence Publish Summary for <TEST_CASE>:
  ✓ DocSync SDLC — <TEST_CASE>  (parent, created/updated)
  ✓ Requirements                (created/updated, id: XXXX)
  ✓ Architecture                (created/updated, id: XXXX)
  ✓ Design Review               (created/updated, id: XXXX)
  ✓ Implementation Plan         (created/updated, id: XXXX)
  ✓ Code Review                 (created/updated, id: XXXX)
  ✓ Verification                (created/updated, id: XXXX)
  ✓ PR Description              (created/updated, id: XXXX)
```

---

## Required Parameters

| Parameter | Source |
|-----------|--------|
| `TEST_CASE` | User input (e.g. `TC-003`) |
| `CONFLUENCE_SPACE_KEY` | User input or `.docsync.yml` |
| `CONFLUENCE_PARENT_PAGE_ID` | Optional; root space if omitted |

## Security
- NEVER hardcode `CONFLUENCE_API_TOKEN` — always read from `os.environ`
- Do not log or echo the token value
