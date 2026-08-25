# DocSync — GitHub PR Creator Skill

## Purpose
Create a GitHub Pull Request for a DocSync SDLC test case implementation using the GitHub MCP tool or `gh` CLI.

## When to Use
- After Phase 8 (PR Creation) is approved
- When the user says "create PR", "open pull request", "merge request", or "push to GitHub"
- When the orchestration agent reaches post-pipeline Action 2

---

## Instructions

### Step 1 — Identify Files to Push
Collect all implementation-related files:

**Source code** (always include):
- `src/docsync/*.py` — all Python source files

**Tests** (include if test files were added/modified):
- `tests/test_*.py`

**Config & docs**:
- `.docsync.yml`
- `docs/${TEST_CASE}/*.md`

### Step 2 — Create Feature Branch

#### Option A — Using GitHub MCP
Use `mcp_github-mcp-se_create_branch` to create:
- Branch name: `docsync/${TEST_CASE}-implementation`
- Base: `main`

#### Option B — Using gh CLI
```bash
git checkout -b docsync/${TEST_CASE}-implementation
git push -u origin HEAD
```

If the branch already exists, skip creation.

### Step 3 — Push Files

#### Option A — GitHub MCP
Use `mcp_github-mcp-se_push_files` to push all collected files to the feature branch.

#### Option B — gh CLI
```bash
git add src/docsync/ tests/ docs/${TEST_CASE}/ .docsync.yml
git commit -m "feat(${TEST_CASE}): implement <short user story title>

- Implements: <USER_STORY>
- All 8 SDLC phases approved
- Test case: ${TEST_CASE}"
git push
```

### Step 4 — Check for Existing PR

#### Option A — GitHub MCP
Use `mcp_github-mcp-se_list_pull_requests` to check if a PR from the branch already exists.

#### Option B — gh CLI
```bash
gh pr list --head docsync/${TEST_CASE}-implementation
```

- If yes → report the existing PR URL, skip creation.
- If no → proceed to create.

### Step 5 — Create Pull Request

#### Option A — GitHub MCP
Use `mcp_github-mcp-se_create_pull_request` with:
```json
{
  "title": "[${TEST_CASE}] <User Story short title>",
  "body": "<contents of docs/${TEST_CASE}/pr-description.md>",
  "head": "docsync/${TEST_CASE}-implementation",
  "base": "main",
  "draft": false
}
```

#### Option B — gh CLI
```bash
gh pr create \
  --title "[${TEST_CASE}] <title>" \
  --body-file "docs/${TEST_CASE}/pr-description.md" \
  --base main \
  --label "sdlc-pipeline"
```

### Step 6 — Report
```
GitHub PR Summary for <TEST_CASE>:
  Branch  : docsync/<TEST_CASE>-implementation
  PR URL  : https://github.com/<owner>/<repo>/pull/<number>
  Title   : [<TEST_CASE>] <title>
  Status  : open
```

---

## Required Parameters

| Parameter | Source |
|-----------|--------|
| `TEST_CASE` | User input (e.g. `TC-003`) |
| `USER_STORY` | From `outputs/${TEST_CASE}/phase-status.json` |
| `GITHUB_OWNER` | User input or `GITHUB_REPOSITORY_OWNER` env |
| `GITHUB_REPO` | User input or `GITHUB_REPOSITORY_NAME` env |

## Security Rules
- Never hardcode tokens. The MCP tool uses env-configured credentials.
- Never log or echo `GITHUB_TOKEN` values.
- Only push to feature branches — never directly to main/master.
