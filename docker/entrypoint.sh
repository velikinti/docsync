#!/usr/bin/env bash
# DocSync Pipeline Entrypoint
# Runs inside Azure Container Instance. Called by Power Automate via ACI connector.
#
# Required environment variables:
#   GITHUB_TOKEN          PAT with repo read/write scope
#   GITHUB_REPO           e.g. "my-org/claude-capstone-project"
#   ANTHROPIC_API_KEY     Anthropic API key
#   CONFLUENCE_API_TOKEN  Atlassian token
#   CONFLUENCE_USER       e.g. user@company.com
#   TC_ID                 e.g. TC-005
#   PHASE                 full | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8
#
# Optional:
#   GITHUB_BRANCH         default: main
#   USER_STORY            required for PHASE=full or PHASE=1
#   FROM_PHASE            resume full pipeline from this phase number

set -euo pipefail

# ── Validate required vars ─────────────────────────────────────────────────────
: "${GITHUB_TOKEN:?GITHUB_TOKEN is required}"
: "${GITHUB_REPO:?GITHUB_REPO is required}"
: "${ANTHROPIC_API_KEY:?ANTHROPIC_API_KEY is required}"
: "${CONFLUENCE_API_TOKEN:?CONFLUENCE_API_TOKEN is required}"
: "${CONFLUENCE_USER:?CONFLUENCE_USER is required}"
: "${TC_ID:?TC_ID is required}"
: "${PHASE:?PHASE is required (full | 1-8)}"

BRANCH="${GITHUB_BRANCH:-main}"

# ── Clone repository ───────────────────────────────────────────────────────────
echo "==> Cloning ${GITHUB_REPO} (branch: ${BRANCH})..."
git clone \
    --branch "$BRANCH" \
    --single-branch \
    --depth 1 \
    "https://${GITHUB_TOKEN}@github.com/${GITHUB_REPO}.git" \
    /workspace

cd /workspace

# ── Install Python dependencies ────────────────────────────────────────────────
echo "==> Installing Python dependencies..."
pip install -e . --quiet --no-warn-script-location

# ── Phase → slash-command mapping ─────────────────────────────────────────────
declare -A PHASE_CMDS=(
    [1]="requirements"
    [2]="architecture"
    [3]="design-review"
    [4]="impl-planning"
    [5]="implementation"
    [6]="code-review"
    [7]="verification"
    [8]="pr"
)

# ── Initialise pipeline scaffold ───────────────────────────────────────────────
# Only needed for a fresh TC or when re-running from phase 1.
if [ "$PHASE" = "full" ] || [ "$PHASE" = "1" ]; then
    echo "==> Initialising pipeline for ${TC_ID}..."
    INIT_ARGS=("-TestCase" "$TC_ID" "-Force")
    [ -n "${USER_STORY:-}" ]  && INIT_ARGS+=("-UserStory"  "${USER_STORY}")
    [ -n "${FROM_PHASE:-}" ]  && INIT_ARGS+=("-FromPhase"  "${FROM_PHASE}")
    pwsh -NonInteractive -File scripts/init-pipeline.ps1 "${INIT_ARGS[@]}"
fi

# ── Build Claude slash command ─────────────────────────────────────────────────
if [ "$PHASE" = "full" ]; then
    CLAUDE_CMD="/pipeline ${TC_ID}"
    [ -n "${USER_STORY:-}" ] && CLAUDE_CMD="${CLAUDE_CMD} \"${USER_STORY}\""
    [ -n "${FROM_PHASE:-}" ] && CLAUDE_CMD="${CLAUDE_CMD} --from ${FROM_PHASE}"
else
    PHASE_NAME="${PHASE_CMDS[$PHASE]:?Unknown PHASE value: $PHASE}"
    CLAUDE_CMD="/${PHASE_NAME} ${TC_ID}"
fi

echo "==> Claude command: ${CLAUDE_CMD}"

# ── Execute pipeline phase ─────────────────────────────────────────────────────
claude --print --dangerously-skip-permissions "${CLAUDE_CMD}"

# ── Commit and push outputs ────────────────────────────────────────────────────
echo "==> Committing outputs to ${BRANCH}..."
git config user.name  "DocSync Pipeline Bot"
git config user.email "docsync-pipeline[bot]@users.noreply.github.com"

git add outputs/ docs/ src/ 2>/dev/null || true

if git diff --staged --quiet; then
    echo "No changes produced — nothing to commit."
else
    git commit -m "ci(pipeline): ${TC_ID} phase ${PHASE} [skip ci]

TC:     ${TC_ID}
Phase:  ${PHASE}
Source: Copilot Studio / Azure Container Instance"
    git push origin "$BRANCH"
    echo "==> Outputs pushed to ${BRANCH}."
fi

echo "==> Pipeline phase complete."
