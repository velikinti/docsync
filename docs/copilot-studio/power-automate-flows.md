# Power Automate Flows — Azure-Native (No GitHub Actions)

All pipeline orchestration runs in **Azure Container Instances (ACI)**.
No GitHub repo settings access is required.

---

## Architecture

```
Copilot Studio (PO/BA)
        │
        ▼
Power Automate Flow
        ├── Pipeline phases  → ACI connector → docker/entrypoint.sh → Claude Code CLI
        └── Approvals        → GitHub Contents API (direct JSON update, no container)
```

Secrets are stored in **Power Platform Environment Variables** (secret type, backed by Dataverse).
No secrets live in GitHub or the container image.

---

## Prerequisites

### 1. Azure Container Registry (ACR)

```bash
# One-time setup — run from a machine with Docker + Azure CLI
az group create --name docsync-rg --location eastus
az acr create --name docsyncreg --resource-group docsync-rg --sku Basic

az acr login --name docsyncreg

docker build -f docker/Dockerfile -t docsync-pipeline .
docker tag docsync-pipeline docsyncreg.azurecr.io/docsync-pipeline:latest
docker push docsyncreg.azurecr.io/docsync-pipeline:latest
```

### 2. ACR credentials for ACI

```bash
az acr credential show --name docsyncreg
# Note the username and one of the passwords — needed in Flow A below.
```

### 3. GitHub Personal Access Token (PAT)

Create a **Fine-grained PAT** scoped to this repository only:
- Permissions: `Contents` (read + write), `Metadata` (read)

This PAT is stored as an Environment Variable, not in GitHub settings.

### 4. Power Platform Environment Variables

Create these in the **Default Solution** (or the solution you use for Copilot Studio):

| Display Name              | Name                        | Type   |
|---------------------------|-----------------------------|--------|
| DocSync — Anthropic Key   | `docsync_anthropic_key`     | Secret |
| DocSync — GitHub PAT      | `docsync_github_pat`        | Secret |
| DocSync — Confluence Token| `docsync_confluence_token`  | Secret |
| DocSync — Confluence User | `docsync_confluence_user`   | Text   |
| DocSync — GitHub Repo     | `docsync_github_repo`       | Text   |
| DocSync — GitHub Branch   | `docsync_github_branch`     | Text   |
| DocSync — ACR Server      | `docsync_acr_server`        | Text   |
| DocSync — ACR Username    | `docsync_acr_username`      | Text   |
| DocSync — ACR Password    | `docsync_acr_password`      | Secret |

Example text values:
- `docsync_github_repo` → `my-org/claude-capstone-project`
- `docsync_github_branch` → `main`
- `docsync_acr_server` → `docsyncreg.azurecr.io`

---

## Flow F1 — Initialize Pipeline

**Called by:** Copilot Studio Topic 1 (Create Feature Request)
**No container needed** — reads/writes GitHub Contents API directly. Completes in ~5 seconds.
**Returns:** `tc_id` (string), `message` (string)

```
Trigger: When Copilot Studio calls a flow
  Input: user_story  Text

── Step 1: Get secrets ───────────────────────────────────────────────────────
  Get_PAT    → docsync_github_pat
  Get_Repo   → docsync_github_repo
  Get_Branch → docsync_github_branch

── Step 2: Read master phase-status.json ─────────────────────────────────────
  [HTTP] GET
    URI: https://api.github.com/repos/@{outputs('Get_Repo')?['value']}/contents/outputs%2Fphase-status.json
    Headers: Authorization + Accept + X-GitHub-Api-Version
  Store: raw_b64 = body?['content'], master_sha = body?['sha']

── Step 3: Decode and parse master JSON ──────────────────────────────────────
  [Compose] decoded = base64ToString(body('Get_Master')?['content'])
  [Parse JSON] schema: { active_test_cases: [], test_cases: {}, ... }
  Rename: Parse_Master

── Step 4: Auto-allocate next TC-ID ─────────────────────────────────────────
  [Compose]
    Expression:
      concat('TC-', padLeft(string(add(length(body('Parse_Master')?['active_test_cases']), 1)), 3, '0'))
    Example: active_test_cases has 5 items → outputs 'TC-006'
  Rename: New_TC_ID

── Step 5: Capture timestamp ─────────────────────────────────────────────────
  [Compose] Expression: utcNow('yyyy-MM-ddTHH:mm:ssZ')
  Rename: Timestamp

── Step 6: Build per-TC phase-status.json content ────────────────────────────
  [Compose]
    Expression (all phases start as PENDING):
      concat('{"test_case_id":"',outputs('New_TC_ID'),'","user_story":"',triggerBody()['text'],'","pipeline_status":"IN_PROGRESS","initialized_at":"',outputs('Timestamp'),'","current_phase":1,"phases":{"1":{"name":"Requirements","phase_folder":"phase-1-requirements","status":"PENDING","output_archive":"outputs/',outputs('New_TC_ID'),'/phase-1-requirements/output.md","approval_file":"outputs/',outputs('New_TC_ID'),'/phase-1-requirements/approval.json"},"2":{"name":"Architecture","phase_folder":"phase-2-architecture","status":"PENDING","output_archive":"outputs/',outputs('New_TC_ID'),'/phase-2-architecture/output.md","approval_file":"outputs/',outputs('New_TC_ID'),'/phase-2-architecture/approval.json"},"3":{"name":"Design Review","phase_folder":"phase-3-design-review","status":"PENDING","output_archive":"outputs/',outputs('New_TC_ID'),'/phase-3-design-review/output.md","approval_file":"outputs/',outputs('New_TC_ID'),'/phase-3-design-review/approval.json"},"4":{"name":"Implementation Planning","phase_folder":"phase-4-impl-planning","status":"PENDING","output_archive":"outputs/',outputs('New_TC_ID'),'/phase-4-impl-planning/output.md","approval_file":"outputs/',outputs('New_TC_ID'),'/phase-4-impl-planning/approval.json"},"5":{"name":"Implementation","phase_folder":"phase-5-implementation","status":"PENDING","output_archive":"outputs/',outputs('New_TC_ID'),'/phase-5-implementation/output.md","approval_file":"outputs/',outputs('New_TC_ID'),'/phase-5-implementation/approval.json"},"6":{"name":"Code Review","phase_folder":"phase-6-code-review","status":"PENDING","output_archive":"outputs/',outputs('New_TC_ID'),'/phase-6-code-review/output.md","approval_file":"outputs/',outputs('New_TC_ID'),'/phase-6-code-review/approval.json"},"7":{"name":"Verification","phase_folder":"phase-7-verification","status":"PENDING","output_archive":"outputs/',outputs('New_TC_ID'),'/phase-7-verification/output.md","approval_file":"outputs/',outputs('New_TC_ID'),'/phase-7-verification/approval.json"},"8":{"name":"PR Creation","phase_folder":"phase-8-pr","status":"PENDING","output_archive":"outputs/',outputs('New_TC_ID'),'/phase-8-pr/output.md","approval_file":"outputs/',outputs('New_TC_ID'),'/phase-8-pr/approval.json"}}}')
  Rename: New_TC_Status_JSON

── Step 7: Write per-TC phase-status.json to GitHub ─────────────────────────
  [HTTP] PUT
    URI: https://api.github.com/repos/@{outputs('Get_Repo')?['value']}/contents/outputs/@{outputs('New_TC_ID')}%2Fphase-status.json
    Headers: Authorization + Content-Type: application/json + Accept + X-GitHub-Api-Version
    Body:
      {
        "message": "chore: init pipeline for @{outputs('New_TC_ID')} [skip ci]",
        "content": "@{base64(outputs('New_TC_Status_JSON'))}",
        "branch":  "@{outputs('Get_Branch')?['value']}"
      }
    ▎ No "sha" field — this is a new file.

── Step 8: Build updated master JSON ─────────────────────────────────────────
  [Compose]
    Expression:
      setProperty(
        setProperty(
          setProperty(body('Parse_Master'), 'last_updated', outputs('Timestamp')),
          'active_test_cases',
          union(body('Parse_Master')?['active_test_cases'], array(outputs('New_TC_ID')))
        ),
        'test_cases',
        setProperty(body('Parse_Master')?['test_cases'], outputs('New_TC_ID'), createObject(
          'user_story',       triggerBody()['text'],
          'pipeline_status',  'IN_PROGRESS',
          'status_file',      concat('outputs/', outputs('New_TC_ID'), '/phase-status.json'),
          'started_at',       outputs('Timestamp')
        ))
      )
  Rename: Updated_Master_JSON

── Step 9: Write updated master phase-status.json ────────────────────────────
  [HTTP] PUT
    URI: https://api.github.com/repos/@{outputs('Get_Repo')?['value']}/contents/outputs%2Fphase-status.json
    Headers: Authorization + Content-Type: application/json + Accept + X-GitHub-Api-Version
    Body:
      {
        "message": "chore: register @{outputs('New_TC_ID')} in master status [skip ci]",
        "content": "@{base64(string(outputs('Updated_Master_JSON')))}",
        "sha":     "@{outputs('master_sha')}",
        "branch":  "@{outputs('Get_Branch')?['value']}"
      }

── Step 10: Return to Copilot Studio ─────────────────────────────────────────
  [Return value(s)]
    tc_id   = @{outputs('New_TC_ID')}
    message = Ticket @{outputs('New_TC_ID')} initialized. Ready to run Phase 1.
```

---

## Flow A — Trigger DocSync Phase (ACI)

**Called by:** Copilot Studio Topics 1 (Start Pipeline)
**Returns:** `container_group_name` (string), `status` (Succeeded | Failed), `log_tail` (string)

### Steps

```
Trigger: When Copilot Studio calls a flow
  Inputs:
    tc_id        Text   (e.g. TC-005)
    phase        Text   (full | 1 | 2 | … | 8)
    user_story   Text   (optional)
    from_phase   Text   (optional)

── Step 1: Get Environment Variables ──────────────────────────────────────────
  [Get environment variable value] — docsync_anthropic_key
  [Get environment variable value] — docsync_github_pat
  [Get environment variable value] — docsync_confluence_token
  [Get environment variable value] — docsync_confluence_user
  [Get environment variable value] — docsync_github_repo
  [Get environment variable value] — docsync_github_branch
  [Get environment variable value] — docsync_acr_server
  [Get environment variable value] — docsync_acr_username
  [Get environment variable value] — docsync_acr_password

── Step 2: Build unique container group name ──────────────────────────────────
  [Compose]
    Name: container-group-name
    Value: concat('docsync-', toLower(triggerBody()?['tc_id']), '-ph',
                  triggerBody()?['phase'], '-',
                  substring(utcNow('yyyyMMddHHmmss'), 8, 6))
    Example output: docsync-tc005-phfull-142305

── Step 3: Create ACI container group ────────────────────────────────────────
  [Azure Container Instance — Create or update a container group]
    Subscription:       <your subscription>
    Resource group:     docsync-rg
    Container group:    @{outputs('container-group-name')}
    Location:           eastus
    OS type:            Linux
    Restart policy:     Never
    Image:              @{outputs('docsync_acr_server')}/docsync-pipeline:latest
    Registry server:    @{outputs('docsync_acr_server')}
    Registry username:  @{outputs('docsync_acr_username')}
    Registry password:  @{outputs('docsync_acr_password')}
    CPU:                2
    Memory (GB):        4
    Environment variables:
      GITHUB_TOKEN          = @{outputs('docsync_github_pat')}
      GITHUB_REPO           = @{outputs('docsync_github_repo')}
      GITHUB_BRANCH         = @{outputs('docsync_github_branch')}
      ANTHROPIC_API_KEY     = @{outputs('docsync_anthropic_key')}
      CONFLUENCE_API_TOKEN  = @{outputs('docsync_confluence_token')}
      CONFLUENCE_USER       = @{outputs('docsync_confluence_user')}
      TC_ID                 = @{triggerBody()?['tc_id']}
      PHASE                 = @{triggerBody()?['phase']}
      USER_STORY            = @{triggerBody()?['user_story']}
      FROM_PHASE            = @{triggerBody()?['from_phase']}

── Step 4: Poll until container finishes ─────────────────────────────────────
  [Do Until]
    Condition: container state != Running
    Limit: 60 minutes / 60 iterations

    Inside loop:
      [Delay] 60 seconds
      [Azure Container Instance — Get container group]
        Container group: @{outputs('container-group-name')}
      Save: @{body('Get_container_group')?['properties']?['containers']?[0]?['properties']?['instanceView']?['currentState']?['state']}
      → stored as: container_state

── Step 5: Get logs ──────────────────────────────────────────────────────────
  [Azure Container Instance — List logs]
    Container group: @{outputs('container-group-name')}
    Container name:  docsync-pipeline   (first container in the group)
    Tail:            50

── Step 6: Delete container group (cleanup) ──────────────────────────────────
  [Azure Container Instance — Delete container group]
    Container group: @{outputs('container-group-name')}

── Step 7: Return to Copilot Studio ──────────────────────────────────────────
  [Return value(s) to Power Virtual Agents]
    status   = @{body('Get_container_group')?['properties']?['containers']?[0]?['properties']?['instanceView']?['currentState']?['state']}
    log_tail = @{body('List_logs')?['content']}
```

---

## Flow B — Get Phase Status

**Called by:** Copilot Studio Topic 2 (Check Status)
**No container needed** — reads directly from the repo via GitHub Contents API.

```
Trigger: When Copilot Studio calls a flow
  Input: tc_id  Text

── Step 1: Get GitHub PAT ────────────────────────────────────────────────────
  [Get environment variable value] — docsync_github_pat
  [Get environment variable value] — docsync_github_repo

── Step 2: Read phase-status.json ────────────────────────────────────────────
  [HTTP]
    Method:  GET
    URI:     https://api.github.com/repos/@{outputs('docsync_github_repo')}/contents/outputs/@{triggerBody()?['tc_id']}/phase-status.json
    Headers:
      Authorization:  Bearer @{outputs('docsync_github_pat')}
      Accept:         application/vnd.github.v3+json
      X-GitHub-Api-Version: 2022-11-28

── Step 3: Decode base64 content ─────────────────────────────────────────────
  [Compose]
    Value: base64ToString(body('HTTP')?['content'])

── Step 4: Return to Copilot Studio ──────────────────────────────────────────
  [Return value(s)]
    status_json = @{outputs('Compose')}
    sha         = @{body('HTTP')?['sha']}   ← needed by Flow C
```

---

## Flow C — Approve Phase (direct GitHub Contents API, no container)

**Called by:** Copilot Studio Topic 4 (Approve / Reject Phase)
Updates `outputs/{tc_id}/phase-status.json` and writes `approval.json` directly via the GitHub Contents API.
No ACI spin-up — completes in ~3 seconds.

```
Trigger: When Copilot Studio calls a flow
  Inputs:
    tc_id     Text
    phase     Text   (1–8)
    decision  Text   (APPROVED | REJECTED)
    reason    Text   (optional)

── Step 1: Fetch current phase-status.json ───────────────────────────────────
  [HTTP] GET (same as Flow B Step 2)
  Store: raw_content_b64 = body?['content'], sha = body?['sha']

── Step 2: Decode and parse JSON ─────────────────────────────────────────────
  [Compose] decoded = base64ToString(raw_content_b64)
  [Parse JSON] schema: { phases: {}, pipeline_status: "", current_phase: 0, ... }

── Step 3: Build updated status object ───────────────────────────────────────
  [Compose] updated_status
  Expression (update decision inline):
    Use setProperty() expressions to update:
      phases.<phase>.status       → decision (APPROVED | REJECTED)
      phases.<phase>.approved_at  → utcNow()     (if APPROVED)
      phases.<phase>.rejected_at  → utcNow()     (if REJECTED)
      phases.<phase>.rejection_reason → reason   (if REJECTED)
      current_phase               → add(int(phase), 1)  (if APPROVED and phase < 8)
      pipeline_status             → 'COMPLETE'   (if APPROVED and phase == 8)

── Step 4: Write updated phase-status.json ───────────────────────────────────
  [HTTP]
    Method:  PUT
    URI:     https://api.github.com/repos/@{outputs('docsync_github_repo')}/contents/outputs/@{triggerBody()?['tc_id']}/phase-status.json
    Headers:
      Authorization:        Bearer @{outputs('docsync_github_pat')}
      Content-Type:         application/json
      X-GitHub-Api-Version: 2022-11-28
    Body:
      {
        "message": "ci(approval): @{triggerBody()?['decision']} phase @{triggerBody()?['phase']} for @{triggerBody()?['tc_id']} [skip ci]",
        "content": "@{base64(string(outputs('updated_status')))}",
        "sha":     "@{outputs('sha')}",
        "branch":  "@{outputs('docsync_github_branch')}"
      }

── Step 5: Write approval.json ───────────────────────────────────────────────
  Phase folder map (Switch on phase):
    1 → phase-1-requirements   5 → phase-5-implementation
    2 → phase-2-architecture   6 → phase-6-code-review
    3 → phase-3-design-review  7 → phase-7-verification
    4 → phase-4-impl-planning  8 → phase-8-pr

  [HTTP]
    Method:  PUT
    URI:     https://api.github.com/repos/@{outputs('docsync_github_repo')}/contents/outputs/@{triggerBody()?['tc_id']}/@{outputs('phase_folder')}/approval.json
    Body:
      {
        "message": "ci(approval): write approval record [skip ci]",
        "content": "@{base64(string(createObject(
            'test_case_id',   triggerBody()?['tc_id'],
            'phase',          int(triggerBody()?['phase']),
            'decision',       triggerBody()?['decision'],
            'decided_at',     utcNow(),
            'reviewer_notes', coalesce(triggerBody()?['reason'], 'No additional notes.')
        )))}",
        "branch": "@{outputs('docsync_github_branch')}"
      }

── Step 6: Return to Copilot Studio ──────────────────────────────────────────
  [Return value(s)]
    success  = true
    decision = @{triggerBody()?['decision']}
```

---

## Flow D — Get Phase Output

**Called by:** Copilot Studio Topic 3 (Review Phase Output)
Reads `outputs/{tc_id}/{phase_folder}/output.md` from the repo.

```
Trigger: When Copilot Studio calls a flow
  Inputs: tc_id Text, phase_num Text

── Step 1: Resolve phase folder (Switch) ─────────────────────────────────────
  1 → phase-1-requirements       5 → phase-5-implementation
  2 → phase-2-architecture       6 → phase-6-code-review
  3 → phase-3-design-review      7 → phase-7-verification
  4 → phase-4-impl-planning      8 → phase-8-pr

── Step 2: Fetch output.md ───────────────────────────────────────────────────
  [HTTP] GET
    URI: https://api.github.com/repos/@{outputs('docsync_github_repo')}/contents/outputs/@{triggerBody()?['tc_id']}/@{outputs('phase_folder')}/output.md
    Headers: Authorization: Bearer @{outputs('docsync_github_pat')}

── Step 3: Decode content ────────────────────────────────────────────────────
  [Compose] base64ToString(body('HTTP')?['content'])
  Trim to first 3000 chars: substring(outputs('Compose'), 0, 3000)

── Step 4: Return ────────────────────────────────────────────────────────────
  output_content = @{outputs('Compose_trim')}
```

---

## Summary — What needs GitHub admin access

| Task | Needs admin? |
|------|-------------|
| Push workflow YAML files | No — just write access |
| Add repo secrets | **Yes — replaced by Power Platform Env Vars** |
| Create GitHub PAT | No — any user can create their own PAT |
| Create ACR / ACI | No — Azure subscription access only |
| Power Platform Env Vars | No — solution maker role sufficient |
