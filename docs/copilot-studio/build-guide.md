# Copilot Studio — Step-by-Step Build Guide (Azure-Native)

DocSync SDLC No-Code PO/BA Interface — No GitHub Admin Required

Total estimated time: ~4 hours
Build order: Prerequisites → Azure Setup → 5 Flows → Copilot → 6 Topics → Publish

---

## PHASE 0 — Prerequisites (30 min)

### 0.1 Create GitHub Personal Access Token (Fine-Grained)

1. Go to GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens
2. Click Generate new token
3. Name: `docsync-copilot-studio`
4. Expiration: 90 days
5. Repository access: Only select repositories → choose your repo
6. Permissions:
   - Contents → Read and write
   - Metadata → Read-only
7. Click Generate token → copy and save (shown once only)

### 0.2 Collect required values before you start

Record these — you will paste them repeatedly:

| Value | Where to find it | Example |
|---|---|---|
| GitHub owner | Your GitHub username | `PraveenEruvanti` |
| GitHub repo | Repository name | `Claude-Capstone-Project` |
| GitHub PAT | From step 0.1 | `github_pat_11A...` |
| Anthropic API key | platform.anthropic.com → API Keys | `sk-ant-api03-...` |
| Confluence token | id.atlassian.net → Security → API tokens | `ATATT3x...` |
| Confluence user | Your Atlassian email | `you@company.com` |
| ACR server | After step 0.3 | `docsyncreg.azurecr.io` |
| ACR username | After step 0.3 | `docsyncreg` |
| ACR password | After step 0.3 | (from az acr credential show) |

### 0.3 Build and push Docker image (one-time, ~15 min)

Open PowerShell and run in order:

```powershell
# Log in to your personal Azure account
az login

# Create Azure resources
az group create --name docsync-rg --location eastus

az acr create `
  --name docsyncreg `
  --resource-group docsync-rg `
  --sku Basic `
  --admin-enabled true

# Build and push the image (run from repo root)
az acr login --name docsyncreg

docker build -f docker/Dockerfile -t docsync-pipeline .

docker tag docsync-pipeline docsyncreg.azurecr.io/docsync-pipeline:latest
docker push docsyncreg.azurecr.io/docsync-pipeline:latest

# Save these credentials for step 0.4
az acr credential show --name docsyncreg
```

Copy the `username` and `passwords[0].value` from the output.

### 0.4 Create Power Platform Environment Variables (10 min)

1. Go to https://make.powerapps.com
2. Solutions → Default Solution → + New → More → Environment variable
3. Create all 9 variables below — use type **Secret** for tokens/passwords, **Text** for the rest:

| Display Name | Schema Name | Type | Value |
|---|---|---|---|
| DocSync GitHub PAT | `docsync_github_pat` | Secret | PAT from 0.1 |
| DocSync Anthropic Key | `docsync_anthropic_key` | Secret | Anthropic key |
| DocSync Confluence Token | `docsync_confluence_token` | Secret | Atlassian token |
| DocSync Confluence User | `docsync_confluence_user` | Text | your@email.com |
| DocSync GitHub Repo | `docsync_github_repo` | Text | `owner/repo-name` |
| DocSync GitHub Branch | `docsync_github_branch` | Text | `main` |
| DocSync ACR Server | `docsync_acr_server` | Text | `docsyncreg.azurecr.io` |
| DocSync ACR Username | `docsync_acr_username` | Text | `docsyncreg` |
| DocSync ACR Password | `docsync_acr_password` | Secret | ACR password from 0.3 |

### 0.5 Open both portals

1. Power Automate: https://make.powerautomate.com — sign in, confirm correct environment (top-right)
2. Copilot Studio: https://copilotstudio.microsoft.com — same account, same environment

---

## ► Reusable pattern — Get secrets at the start of every flow

Every flow starts with these steps. Do this block first in each flow, then continue with the flow-specific steps.

**Add these actions at the top of every flow:**

```
[Microsoft Dataverse — Get Environment Variable Value]
  → Schema name: docsync_github_pat
  → Rename step: Get_PAT

[Microsoft Dataverse — Get Environment Variable Value]
  → Schema name: docsync_github_repo
  → Rename step: Get_Repo

[Microsoft Dataverse — Get Environment Variable Value]
  → Schema name: docsync_github_branch
  → Rename step: Get_Branch
```

Reference in HTTP headers:
- Authorization header value: `Bearer @{outputs('Get_PAT')?['value']}`
- Repo in URIs: `@{outputs('Get_Repo')?['value']}`
- Branch: `@{outputs('Get_Branch')?['value']}`

▎ If "Get Environment Variable Value" is not visible: search "Dataverse" → look under Microsoft Dataverse actions → "Get a row by ID" → Table: Environment Variable Values → Row ID: the schema name.

---

## PHASE 1 — Flow F2: Get Ticket Status (20 min)

▎ Reads `outputs/{TC-ID}/phase-status.json` from GitHub and returns it.

### 1.1 Create the flow

1. Power Automate → Create → Instant cloud flow
2. Name: `DocSync - Get Ticket Status`
3. Trigger: search "Copilot Studio" → select **Run a flow from Copilot** → Create

### 1.2 Add trigger input

1. Click the trigger card **Run a flow from Copilot**
2. Click + Add an input → Text
3. Name: `tc_id` | Description: `Ticket ID e.g. TC-004`

### 1.3 Add Get Secrets steps

Follow the **► Reusable pattern** above — add Get_PAT, Get_Repo, Get_Branch.

### 1.4 HTTP — Read phase-status.json from GitHub

1. + New step → search HTTP → select **HTTP**
2. Configure:
   - Method: `GET`
   - URI:
     ```
     https://api.github.com/repos/@{outputs('Get_Repo')?['value']}/contents/outputs/@{triggerBody()['text']}%2Fphase-status.json
     ```
   - Headers — add two:
     - `Authorization` → `Bearer @{outputs('Get_PAT')?['value']}`
     - `Accept` → `application/vnd.github+json`
     - `X-GitHub-Api-Version` → `2022-11-28`
3. Rename step: `Get_Status_File`

### 1.5 Decode base64 file content

1. + New step → **Compose** (Data Operations)
2. Inputs — switch to Expression tab, paste:
   ```
   base64ToString(body('Get_Status_File')?['content'])
   ```
3. Rename step: `Decode_Status`

### 1.6 Parse the decoded JSON

1. + New step → **Parse JSON**
2. Content: select `Outputs` from the Decode_Status step
3. Schema: click **Generate from sample** → paste:
```json
{
  "test_case_id": "TC-002",
  "user_story": "US-002: ...",
  "pipeline_status": "COMPLETE",
  "current_phase": 8,
  "phases": {
    "1": { "name": "Requirements", "status": "APPROVED", "phase_folder": "phase-1-requirements" },
    "2": { "name": "Architecture", "status": "APPROVED", "phase_folder": "phase-2-architecture" },
    "3": { "name": "Design Review", "status": "APPROVED", "phase_folder": "phase-3-design-review" },
    "4": { "name": "Implementation Planning", "status": "APPROVED", "phase_folder": "phase-4-impl-planning" },
    "5": { "name": "Implementation", "status": "APPROVED", "phase_folder": "phase-5-implementation" },
    "6": { "name": "Code Review", "status": "APPROVED", "phase_folder": "phase-6-code-review" },
    "7": { "name": "Verification", "status": "APPROVED", "phase_folder": "phase-7-verification" },
    "8": { "name": "PR Creation", "status": "APPROVED", "phase_folder": "phase-8-pr" }
  }
}
```
4. Click Done. Rename step: `Parse_Status`

### 1.7 Add Respond to Copilot

1. + New step → search "Respond to Copilot" → select it
2. + Add an output → **Text** → Name: `pipeline_status` → Value: select `pipeline_status` from Parse_Status
3. + Add an output → **Number** → Name: `current_phase` → Value: select `current_phase`
4. + Add an output → **Text** → Name: `user_story` → Value: select `user_story`
5. + Add an output → **Text** → Name: `full_json` → Value: select `Outputs` from Decode_Status
6. + Add an output → **Text** → Name: `sha` → Value: `@{body('Get_Status_File')?['sha']}`

### 1.8 Save and test

1. Click Save
2. Click Test → Manual → Run flow
3. Enter `tc_id`: `TC-002` → Run → verify `pipeline_status` returns `COMPLETE`

---

## PHASE 2 — Flow F3: Get Phase Output (15 min)

▎ Reads `outputs/{TC-ID}/{phase-folder}/output.md` and returns the markdown.

### 2.1 Create the flow

1. Name: `DocSync - Get Phase Output`
2. Trigger: **Run a flow from Copilot**

### 2.2 Add trigger inputs

Add two text inputs:
- `tc_id` — e.g. TC-004
- `phase_num` — e.g. 3

### 2.3 Add Get Secrets steps

Add Get_PAT, Get_Repo, Get_Branch (reusable pattern).

### 2.4 Map phase number to folder name

1. + New step → **Compose**
2. Inputs — Expression tab:
   ```
   array(['phase-1-requirements','phase-2-architecture','phase-3-design-review','phase-4-impl-planning','phase-5-implementation','phase-6-code-review','phase-7-verification','phase-8-pr'])[sub(int(triggerBody()['text_1']),1)]
   ```
3. Rename step: `Get_Folder_Name`

▎ `text_1` refers to the second trigger input (phase_num). Inputs are named `text`, `text_1`, `text_2`... in order.

### 2.5 HTTP — Get output.md

1. + New step → **HTTP**
2. Method: `GET`
3. URI:
   ```
   https://api.github.com/repos/@{outputs('Get_Repo')?['value']}/contents/outputs/@{triggerBody()['text']}%2F@{outputs('Get_Folder_Name')}%2Foutput.md
   ```
4. Headers: Authorization + Accept + X-GitHub-Api-Version (same as Phase 1)
5. Rename: `Get_Output_File`

### 2.6 Decode content

1. + New step → **Compose**
2. Expression:
   ```
   substring(base64ToString(body('Get_Output_File')?['content']),0,3000)
   ```
3. Rename: `Decode_Output`

▎ Truncating to 3000 chars prevents Copilot Studio message overflow. Remove the `substring()` wrapper if you want the full content.

### 2.7 Respond to Copilot

1. Respond to Copilot
2. + Add output → Text → Name: `output_markdown` → Value: Outputs from Decode_Output
3. + Add output → Text → Name: `phase_folder` → Value: Outputs from Get_Folder_Name

### 2.8 Save and test

- `tc_id`: TC-002, `phase_num`: 1 → should return requirements markdown.

---

## PHASE 3 — Flow F5: List All Tickets (15 min)

▎ Reads master `outputs/phase-status.json` and returns all ticket summaries.

### 3.1 Create the flow

1. Name: `DocSync - List All Tickets`
2. Trigger: **Run a flow from Copilot** — no inputs needed

### 3.2 Add Get Secrets steps

Add Get_PAT, Get_Repo (no branch needed here).

### 3.3 HTTP — Get master status file

1. + New step → **HTTP**
2. Method: `GET`
3. URI:
   ```
   https://api.github.com/repos/@{outputs('Get_Repo')?['value']}/contents/outputs%2Fphase-status.json
   ```
4. Headers: Authorization + Accept + X-GitHub-Api-Version
5. Rename: `Get_Master_File`

### 3.4 Decode content

1. + New step → **Compose**
2. Expression: `base64ToString(body('Get_Master_File')?['content'])`
3. Rename: `Decode_Master`

### 3.5 Parse to extract active tickets

1. + New step → **Parse JSON**
2. Content: Outputs from Decode_Master
3. Schema (Generate from sample → paste):
```json
{
  "active_test_cases": ["TC-001","TC-002"],
  "last_updated": "2026-08-31T10:00:00Z",
  "test_cases": {
    "TC-001": { "pipeline_status": "COMPLETE", "user_story": "US-001: ..." },
    "TC-002": { "pipeline_status": "IN_PROGRESS", "user_story": "US-002: ..." }
  }
}
```
4. Rename: `Parse_Master`

### 3.6 Format active tickets list

1. + New step → **Compose**
2. Expression:
   ```
   join(body('Parse_Master')?['active_test_cases'], ' | ')
   ```
3. Rename: `Format_Active_TCs`

### 3.7 Respond to Copilot

1. Respond to Copilot
2. + Add output → Text → Name: `active_tcs` → Value: Outputs from Format_Active_TCs
3. + Add output → Text → Name: `master_json` → Value: Outputs from Decode_Master

### 3.8 Save and test

- Run with no inputs → verify returns list like `TC-001 | TC-002 | TC-003`.

---

## PHASE 4 — Flow F4: Record Approval / Rejection (30 min)

▎ Writes `approval.json` and updates `phase-status.json` directly via GitHub Contents API.
▎ No GitHub Actions required — all updates happen inside this flow.

### 4.1 Create the flow

1. Name: `DocSync - Record Phase Decision`
2. Trigger: **Run a flow from Copilot**
3. Add 4 inputs:
   - `tc_id` (Text)
   - `phase_num` (Text)
   - `decision` (Text) — APPROVED or REJECTED
   - `reason` (Text)

### 4.2 Add Get Secrets steps

Add Get_PAT, Get_Repo, Get_Branch.

### 4.3 Get folder and display name

1. + New step → **Compose** → Expression:
   ```
   array(['phase-1-requirements','phase-2-architecture','phase-3-design-review','phase-4-impl-planning','phase-5-implementation','phase-6-code-review','phase-7-verification','phase-8-pr'])[sub(int(triggerBody()['text_1']),1)]
   ```
   Rename: `Get_Folder_Name`

2. + New step → **Compose** → Expression:
   ```
   array(['Requirements','Architecture','Design Review','Implementation Planning','Implementation','Code Review','Verification','PR Creation'])[sub(int(triggerBody()['text_1']),1)]
   ```
   Rename: `Get_Phase_Name`

### 4.4 Get current timestamp

1. + New step → **Compose** → Expression: `utcNow('yyyy-MM-ddTHH:mm:ssZ')`
2. Rename: `Get_Timestamp`

### 4.5 Check if approval.json already exists (get SHA)

1. + New step → **HTTP**
2. Method: `GET`
3. URI:
   ```
   https://api.github.com/repos/@{outputs('Get_Repo')?['value']}/contents/outputs/@{triggerBody()['text']}/@{outputs('Get_Folder_Name')}/approval.json
   ```
4. Headers: Authorization + Accept + X-GitHub-Api-Version
5. Rename: `Get_Approval_SHA`
6. Expand **Show advanced options** → set **Suppress HTTP errors**: `Yes`
   ▎ This prevents the flow from failing if the file doesn't exist yet.

### 4.6 Extract SHA (empty string if file is new)

1. + New step → **Condition**
2. Left: `@{outputs('Get_Approval_SHA')?['statusCode']}` | Equals | `200`

   **If yes branch:**
   1. + New step → **Compose** → Expression: `body('Get_Approval_SHA')?['sha']`
   2. Rename: `Extract_Approval_SHA`

   **If no branch:**
   1. + New step → **Compose** → Inputs: *(leave empty string)*
   2. Rename: `Extract_Approval_SHA`

### 4.7 Build approval.json content

After the Condition, add:

1. + New step → **Compose**
2. Inputs (switch to **Expression** tab):
   ```
   concat('{"test_case_id":"',triggerBody()['text'],'","phase":',int(triggerBody()['text_1']),',"phase_folder":"',outputs('Get_Folder_Name'),'","phase_name":"',outputs('Get_Phase_Name'),'","decision":"',triggerBody()['text_2'],'","decided_at":"',outputs('Get_Timestamp'),'","reviewer_notes":"',if(equals(triggerBody()['text_3'],''),'No additional notes.',triggerBody()['text_3']),'"}')
   ```
3. Rename: `Build_Approval_JSON`

### 4.8 Write approval.json to GitHub

1. + New step → **HTTP**
2. Method: `PUT`
3. URI:
   ```
   https://api.github.com/repos/@{outputs('Get_Repo')?['value']}/contents/outputs/@{triggerBody()['text']}/@{outputs('Get_Folder_Name')}/approval.json
   ```
4. Headers: Authorization + Accept + Content-Type: `application/json` + X-GitHub-Api-Version
5. Body:
   ```json
   {
     "message": "chore: @{triggerBody()['text_2']} phase @{triggerBody()['text_1']} for @{triggerBody()['text']} [skip ci]",
     "content": "@{base64(outputs('Build_Approval_JSON'))}",
     "branch": "@{outputs('Get_Branch')?['value']}",
     "sha": "@{outputs('Extract_Approval_SHA')}"
   }
   ```
6. Rename: `Write_Approval`

### 4.9 Read current phase-status.json (with SHA)

1. + New step → **HTTP** → Method: GET
2. URI:
   ```
   https://api.github.com/repos/@{outputs('Get_Repo')?['value']}/contents/outputs/@{triggerBody()['text']}%2Fphase-status.json
   ```
3. Headers: same auth headers
4. Rename: `Get_Phase_Status`

### 4.10 Decode status JSON

1. + New step → **Compose**
2. Expression: `base64ToString(body('Get_Phase_Status')?['content'])`
3. Rename: `Decode_Phase_Status`

### 4.11 Build updated status JSON using string replace

▎ Power Automate cannot mutate nested JSON natively. Use string replace on the specific phase status field.

1. + New step → **Compose**
2. Expression (replaces `"status":"PENDING"` or `"status":"PENDING_APPROVAL"` for this phase with the new decision):
   ```
   replace(replace(outputs('Decode_Phase_Status'),concat('"',triggerBody()['text_1'],'":{"name":"',outputs('Get_Phase_Name'),'","phase_folder":"',outputs('Get_Folder_Name'),'","status":"PENDING"'),concat('"',triggerBody()['text_1'],'":{"name":"',outputs('Get_Phase_Name'),'","phase_folder":"',outputs('Get_Folder_Name'),'","status":"',triggerBody()['text_2'],'"')),concat('"',triggerBody()['text_1'],'":{"name":"',outputs('Get_Phase_Name'),'","phase_folder":"',outputs('Get_Folder_Name'),'","status":"PENDING_APPROVAL"'),concat('"',triggerBody()['text_1'],'":{"name":"',outputs('Get_Phase_Name'),'","phase_folder":"',outputs('Get_Folder_Name'),'","status":"',triggerBody()['text_2'],'"'))
   ```
3. Rename: `Build_Updated_Status`

▎ This replaces the status field of the specific phase regardless of whether it was PENDING or PENDING_APPROVAL.

### 4.12 Write updated phase-status.json to GitHub

1. + New step → **HTTP**
2. Method: `PUT`
3. URI:
   ```
   https://api.github.com/repos/@{outputs('Get_Repo')?['value']}/contents/outputs/@{triggerBody()['text']}%2Fphase-status.json
   ```
4. Headers: same auth headers + Content-Type: application/json
5. Body:
   ```json
   {
     "message": "chore: update status @{triggerBody()['text_2']} phase @{triggerBody()['text_1']} for @{triggerBody()['text']} [skip ci]",
     "content": "@{base64(outputs('Build_Updated_Status'))}",
     "branch": "@{outputs('Get_Branch')?['value']}",
     "sha": "@{body('Get_Phase_Status')?['sha']}"
   }
   ```
6. Rename: `Write_Phase_Status`

### 4.13 Respond to Copilot

1. Respond to Copilot
2. + Add output → Text → Name: `result`
3. Value:
   ```
   @{triggerBody()['text']} Phase @{triggerBody()['text_1']} (@{outputs('Get_Phase_Name')}) recorded as @{triggerBody()['text_2']}
   ```

### 4.14 Save and test

- `tc_id`: TC-002, `phase_num`: 1, `decision`: APPROVED, `reason`: Looks good
- Check the repo → `outputs/TC-002/phase-1-requirements/approval.json` should appear

---

## PHASE 4b — Flow F1: Initialize Pipeline (15 min)

▎ Creates a new ticket (TC-006, TC-007, …) by writing directly to GitHub via the Contents API.
▎ No container needed — completes in ~5 seconds.

### 4b.1 Create the flow

1. Power Automate → Create → Instant cloud flow
2. Name: `DocSync - Initialize Pipeline`
3. Trigger: **Run a flow from Copilot** → Create

### 4b.2 Add trigger input

1. Click the trigger card **Run a flow from Copilot**
2. + Add an input → Text
3. Name: `user_story` | Description: `Feature user story (e.g. As a developer, I want…)`

### 4b.3 Add Get Secrets steps

Add Get_PAT, Get_Repo, Get_Branch (reusable pattern from top of this guide).

### 4b.4 HTTP — Read master phase-status.json

1. + New step → **HTTP**
2. Method: `GET`
3. URI:
   ```
   https://api.github.com/repos/@{outputs('Get_Repo')?['value']}/contents/outputs%2Fphase-status.json
   ```
4. Headers: Authorization + Accept + X-GitHub-Api-Version
5. Rename: `Get_Master`

### 4b.5 Decode master JSON

1. + New step → **Compose**
2. Expression: `base64ToString(body('Get_Master')?['content'])`
3. Rename: `Decode_Master`

### 4b.6 Parse master JSON

1. + New step → **Parse JSON**
2. Content: Outputs from Decode_Master
3. Schema → Generate from sample → paste:
```json
{
  "active_test_cases": ["TC-001","TC-002"],
  "last_updated": "2026-08-31T10:00:00Z",
  "test_cases": {
    "TC-001": { "user_story": "US-001: ...", "pipeline_status": "COMPLETE", "status_file": "outputs/TC-001/phase-status.json", "started_at": "2026-07-27T09:00:00Z" }
  }
}
```
4. Rename: `Parse_Master`

### 4b.7 Auto-allocate next TC-ID

1. + New step → **Compose**
2. Expression tab:
   ```
   concat('TC-', padLeft(string(add(length(body('Parse_Master')?['active_test_cases']), 1)), 3, '0'))
   ```
3. Rename: `New_TC_ID`

▎ Example: 5 items in active_test_cases → outputs `TC-006`.

### 4b.8 Capture timestamp

1. + New step → **Compose**
2. Expression: `utcNow('yyyy-MM-ddTHH:mm:ssZ')`
3. Rename: `Timestamp`

### 4b.9 Build per-TC phase-status.json content

1. + New step → **Compose**
2. Expression tab — paste this single expression (all phases start as PENDING):
   ```
   concat('{"test_case_id":"',outputs('New_TC_ID'),'","user_story":"',triggerBody()['user_story'],'","pipeline_status":"IN_PROGRESS","initialized_at":"',outputs('Timestamp'),'","current_phase":1,"phases":{"1":{"name":"Requirements","phase_folder":"phase-1-requirements","status":"PENDING","output_archive":"outputs/',outputs('New_TC_ID'),'/phase-1-requirements/output.md","approval_file":"outputs/',outputs('New_TC_ID'),'/phase-1-requirements/approval.json"},"2":{"name":"Architecture","phase_folder":"phase-2-architecture","status":"PENDING","output_archive":"outputs/',outputs('New_TC_ID'),'/phase-2-architecture/output.md","approval_file":"outputs/',outputs('New_TC_ID'),'/phase-2-architecture/approval.json"},"3":{"name":"Design Review","phase_folder":"phase-3-design-review","status":"PENDING","output_archive":"outputs/',outputs('New_TC_ID'),'/phase-3-design-review/output.md","approval_file":"outputs/',outputs('New_TC_ID'),'/phase-3-design-review/approval.json"},"4":{"name":"Implementation Planning","phase_folder":"phase-4-impl-planning","status":"PENDING","output_archive":"outputs/',outputs('New_TC_ID'),'/phase-4-impl-planning/output.md","approval_file":"outputs/',outputs('New_TC_ID'),'/phase-4-impl-planning/approval.json"},"5":{"name":"Implementation","phase_folder":"phase-5-implementation","status":"PENDING","output_archive":"outputs/',outputs('New_TC_ID'),'/phase-5-implementation/output.md","approval_file":"outputs/',outputs('New_TC_ID'),'/phase-5-implementation/approval.json"},"6":{"name":"Code Review","phase_folder":"phase-6-code-review","status":"PENDING","output_archive":"outputs/',outputs('New_TC_ID'),'/phase-6-code-review/output.md","approval_file":"outputs/',outputs('New_TC_ID'),'/phase-6-code-review/approval.json"},"7":{"name":"Verification","phase_folder":"phase-7-verification","status":"PENDING","output_archive":"outputs/',outputs('New_TC_ID'),'/phase-7-verification/output.md","approval_file":"outputs/',outputs('New_TC_ID'),'/phase-7-verification/approval.json"},"8":{"name":"PR Creation","phase_folder":"phase-8-pr","status":"PENDING","output_archive":"outputs/',outputs('New_TC_ID'),'/phase-8-pr/output.md","approval_file":"outputs/',outputs('New_TC_ID'),'/phase-8-pr/approval.json"}}}')
   ```
3. Rename: `New_TC_Status_JSON`

### 4b.10 Write per-TC phase-status.json to GitHub

1. + New step → **HTTP**
2. Method: `PUT`
3. URI:
   ```
   https://api.github.com/repos/@{outputs('Get_Repo')?['value']}/contents/outputs/@{outputs('New_TC_ID')}%2Fphase-status.json
   ```
4. Headers: Authorization + Accept + Content-Type: `application/json` + X-GitHub-Api-Version
5. Body:
   ```json
   {
     "message": "chore: init pipeline for @{outputs('New_TC_ID')} [skip ci]",
     "content": "@{base64(outputs('New_TC_Status_JSON'))}",
     "branch":  "@{outputs('Get_Branch')?['value']}"
   }
   ```
   ▎ No `sha` field — this is always a new file.
6. Rename: `Write_TC_Status`

### 4b.11 Build updated master JSON

1. + New step → **Compose**
2. Expression tab:
   ```
   setProperty(setProperty(setProperty(body('Parse_Master'),'last_updated',outputs('Timestamp')),'active_test_cases',union(body('Parse_Master')?['active_test_cases'],array(outputs('New_TC_ID')))),'test_cases',setProperty(body('Parse_Master')?['test_cases'],outputs('New_TC_ID'),createObject('user_story',triggerBody()['user_story'],'pipeline_status','IN_PROGRESS','status_file',concat('outputs/',outputs('New_TC_ID'),'/phase-status.json'),'started_at',outputs('Timestamp'))))
   ```
3. Rename: `Updated_Master_JSON`

### 4b.12 Write updated master phase-status.json

1. + New step → **HTTP**
2. Method: `PUT`
3. URI:
   ```
   https://api.github.com/repos/@{outputs('Get_Repo')?['value']}/contents/outputs%2Fphase-status.json
   ```
4. Headers: Authorization + Accept + Content-Type: `application/json` + X-GitHub-Api-Version
5. Body:
   ```json
   {
     "message": "chore: register @{outputs('New_TC_ID')} in master status [skip ci]",
     "content": "@{base64(string(outputs('Updated_Master_JSON')))}",
     "sha":     "@{body('Get_Master')?['sha']}",
     "branch":  "@{outputs('Get_Branch')?['value']}"
   }
   ```
6. Rename: `Write_Master`

### 4b.13 Respond to Copilot

1. + New step → **Respond to Copilot**
2. + Add output → Text → Name: `tc_id` → Value: `@{outputs('New_TC_ID')}`
3. + Add output → Text → Name: `message` → Value:
   ```
   Ticket @{outputs('New_TC_ID')} initialized. Ready to run Phase 1.
   ```

### 4b.14 Save and test

1. Click Save → Test → Manual
2. Enter `user_story`: `As a developer, I want X so that Y`
3. Verify:
   - `tc_id` output = next TC in sequence (e.g. `TC-006`)
   - GitHub repo → `outputs/TC-006/phase-status.json` created with all 8 phases as PENDING
   - GitHub repo → `outputs/phase-status.json` master updated with TC-006 entry

---

## PHASE 5 — Flow FA: Trigger Pipeline Phase via ACI (40 min)

▎ Starts an Azure Container Instance that clones the repo and runs Claude Code.
▎ This flow takes 2–5 minutes to complete while the container runs.

### 5.1 Create the flow

1. Name: `DocSync - Trigger Pipeline Phase`
2. Trigger: **Run a flow from Copilot**
3. Add inputs:
   - `tc_id` (Text)
   - `phase` (Text) — full | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8
   - `user_story` (Text) — optional, for full or phase 1
   - `from_phase` (Text) — optional, resume full pipeline from this phase

### 5.2 Add ALL Get Secrets steps

This flow needs all 9 environment variables:

```
Get_PAT            → docsync_github_pat
Get_Anthropic      → docsync_anthropic_key
Get_Confluence_Tok → docsync_confluence_token
Get_Confluence_Usr → docsync_confluence_user
Get_Repo           → docsync_github_repo
Get_Branch         → docsync_github_branch
Get_ACR_Server     → docsync_acr_server
Get_ACR_User       → docsync_acr_username
Get_ACR_Pass       → docsync_acr_password
```

Add one **Microsoft Dataverse — Get Environment Variable Value** step for each.

### 5.3 Build a unique container group name

1. + New step → **Compose**
2. Expression:
   ```
   concat('docsync-',toLower(triggerBody()['text']),'-ph',triggerBody()['text_1'],'-',substring(utcNow('yyyyMMddHHmmss'),8,6))
   ```
3. Rename: `Container_Group_Name`

Example output: `docsync-tc005-phfull-142305`

### 5.4 Create ACI container group

1. + New step → search **Azure Container Instance** → select **Create or update a container group**
2. If prompted to create a connection → sign in with your Azure account → select your subscription
3. Configure:
   - Subscription: your personal Azure subscription
   - Resource group: `docsync-rg`
   - Container group name: `@{outputs('Container_Group_Name')}`
   - Location: `East US`
   - OS type: `Linux`
   - Restart policy: `Never`
   - Container name: `docsync-runner`
   - Image: `@{outputs('Get_ACR_Server')?['value']}/docsync-pipeline:latest`
   - Registry server: `@{outputs('Get_ACR_Server')?['value']}`
   - Registry username: `@{outputs('Get_ACR_User')?['value']}`
   - Registry password: `@{outputs('Get_ACR_Pass')?['value']}`
   - CPU: `2`
   - Memory (GB): `4`
4. Environment variables (add each as a key-value pair):
   | Name | Value |
   |---|---|
   | `GITHUB_TOKEN` | `@{outputs('Get_PAT')?['value']}` |
   | `GITHUB_REPO` | `@{outputs('Get_Repo')?['value']}` |
   | `GITHUB_BRANCH` | `@{outputs('Get_Branch')?['value']}` |
   | `ANTHROPIC_API_KEY` | `@{outputs('Get_Anthropic')?['value']}` |
   | `CONFLUENCE_API_TOKEN` | `@{outputs('Get_Confluence_Tok')?['value']}` |
   | `CONFLUENCE_USER` | `@{outputs('Get_Confluence_Usr')?['value']}` |
   | `TC_ID` | `@{triggerBody()['text']}` |
   | `PHASE` | `@{triggerBody()['text_1']}` |
   | `USER_STORY` | `@{triggerBody()['text_2']}` |
   | `FROM_PHASE` | `@{triggerBody()['text_3']}` |
5. Rename: `Create_Container`

### 5.5 Wait 30 seconds for container to start

1. + New step → **Delay** (Control)
2. Count: `30`, Unit: `Second`

### 5.6 Poll container until it finishes

1. + New step → **Do until** (Control)
2. Configure the loop exit condition:
   - Left value (Expression): `@{body('Get_Container_Status')?['properties']?['containers']?[0]?['properties']?['instanceView']?['currentState']?['state']}`
   - Condition: **is not equal to**
   - Right value: `Running`
3. Limits: Count `60`, Timeout `PT60M`
4. Inside the loop, add:

   **a. Delay**
   - Count: `60`, Unit: `Second`

   **b. Get container group status**
   - + New step → **Azure Container Instance — Get a container group**
   - Subscription: same as above
   - Resource group: `docsync-rg`
   - Container group name: `@{outputs('Container_Group_Name')}`
   - Rename: `Get_Container_Status`

### 5.7 Get container logs

1. After the Do Until loop, + New step → **Azure Container Instance — List logs for a container**
2. Subscription, Resource group: same
3. Container group name: `@{outputs('Container_Group_Name')}`
4. Container name: `docsync-runner`
5. Tail: `30`
6. Rename: `Get_Container_Logs`

### 5.8 Delete the container group (cleanup)

1. + New step → **Azure Container Instance — Delete a container group**
2. Subscription, Resource group: same
3. Container group name: `@{outputs('Container_Group_Name')}`
4. Rename: `Delete_Container`

### 5.9 Respond to Copilot

1. Respond to Copilot
2. + Add output → Text → Name: `status`
3. Value (Expression):
   ```
   body('Get_Container_Status')?['properties']?['containers']?[0]?['properties']?['instanceView']?['currentState']?['state']
   ```
4. + Add output → Text → Name: `log_tail`
5. Value: `@{body('Get_Container_Logs')?['content']}`
6. + Add output → Text → Name: `tc_id`
7. Value: `@{triggerBody()['text']}`

### 5.10 Save and test

1. Click Test → manually enter: `tc_id`: TC-002, `phase`: 1, `user_story`: (blank), `from_phase`: (blank)
2. The flow will take ~3–5 minutes
3. Check `status` output — should return `Succeeded` or `Terminated`
4. Check GitHub repo — `outputs/TC-002/phase-1-requirements/output.md` should be updated

---

## PHASE 6 — Create the Copilot (10 min)

### 6.1 Create a new Copilot

1. Go to https://copilotstudio.microsoft.com
2. Click + Create → New copilot
3. Name: `DocSync Pipeline Assistant`
4. Language: English
5. Click Create

### 6.2 Disable unused system topics

1. Topics tab → System topics
2. Keep: Greeting, Goodbye, Escalate, Fallback
3. Disable: Start Over, Thank You (click the toggle)

### 6.3 Update the Greeting topic

1. Click Greeting → find the first message node
2. Replace with:
```
Hi! I'm the DocSync Pipeline Assistant.

I can help you:
• 🚀 Create a new feature ticket and run the pipeline
• 📊 Check ticket status
• 📄 Review phase outputs
• ✅ Approve a phase
• ❌ Reject a phase
• 📋 List all active tickets

What would you like to do?
```

---

## PHASE 7 — Topic T2: Check Ticket Status (20 min)

### 7.1 Create the topic

1. Topics → + New topic → From blank
2. Name: `Check Ticket Status`

### 7.2 Trigger phrases

Click **Edit** under Trigger → Add:
- `check status`
- `status of TC`
- `what phase is`
- `show me TC`
- `pipeline status`
- `how far is TC`

### 7.3 Question — ask for TC ID

1. + node → **Ask a question**
2. Question text: `Which ticket would you like to check? (e.g. TC-004)`
3. Identify: **User's entire response**
4. Save response as: create variable `Var_TCID` (Text)

### 7.4 Action — call F2

1. + node → **Call an action**
2. Select: `DocSync - Get Ticket Status` from the list
3. Set input `tc_id` = `Var_TCID`
4. Map outputs:
   - `pipeline_status` → create var `Var_PipelineStatus`
   - `current_phase` → create var `Var_CurrentPhase`
   - `user_story` → create var `Var_UserStory`

### 7.5 Message node — show result

1. + node → **Send a message**
2. Text:
```
📋 **{Var_TCID}**
Story: {Var_UserStory}
Pipeline: {Var_PipelineStatus}
Current Phase: {Var_CurrentPhase} of 8
```

### 7.6 Quick replies

1. Below the message, + node → **Add quick replies**
2. Add: `Review Phase Output` | `Approve a Phase` | `Reject a Phase` | `Main Menu`

### 7.7 Save and test

Click Test → type `status of TC-002` → confirm it returns status data.

---

## PHASE 8 — Topic T3: Review Phase Output (15 min)

### 8.1 Create topic

1. Name: `Review Phase Output`
2. Trigger phrases:
   - `show output` | `review phase` | `what did phase produce`
   - `show requirements` | `show architecture` | `read phase`

### 8.2 Question — TC ID

Same as T2 step 7.3 → variable `Var_TCID`

### 8.3 Question — phase number

1. + node → **Ask a question**
2. Text:
```
Which phase? Enter a number 1–8:
1 = Requirements
2 = Architecture
3 = Design Review
4 = Implementation Planning
5 = Implementation
6 = Code Review
7 = Verification
8 = PR Creation
```
3. Identify: **Number**
4. Save as: `Var_PhaseNum`

### 8.4 Call F3

1. Call an action → `DocSync - Get Phase Output`
2. Inputs: `tc_id` = `Var_TCID`, `phase_num` = `Var_PhaseNum`
3. Outputs: `output_markdown` → `Var_OutputMD`, `phase_folder` → `Var_PhaseFolder`

### 8.5 Message

```
📄 **{Var_TCID} — Phase {Var_PhaseNum} Output**

{Var_OutputMD}
```

### 8.6 Quick replies

`Approve This Phase` | `Reject This Phase` | `Check Status` | `Main Menu`

---

## PHASE 9 — Topic T4: Approve Phase (15 min)

### 9.1 Create topic

1. Name: `Approve Phase`
2. Trigger phrases:
   - `approve phase` | `sign off` | `approve TC` | `mark approved` | `looks good`

### 9.2 Collect inputs

Three question nodes:
1. `Which ticket?` → `Var_TCID` (User's entire response)
2. `Which phase number? (1–8)` → `Var_PhaseNum` (Number)
3. `Any reviewer notes? (type "none" to skip)` → `Var_Reason` (User's entire response)

### 9.3 Confirmation step

1. + node → **Ask a question**
2. Text: `Confirm: Approve **{Var_TCID}** Phase **{Var_PhaseNum}**?`
3. Identify: **Multiple choice options**
4. Options: `Yes, approve` | `No, cancel`
5. Save as: `Var_Confirm`

### 9.4 Condition branch

1. + node → **Condition**
2. `Var_Confirm` **is equal to** `Yes, approve`

   **Yes branch:**
   Continue to 9.5

   **No branch:**
   + node → Message: `Cancelled. No changes made.` → End topic

### 9.5 Call F4 (approve)

1. Call an action → `DocSync - Record Phase Decision`
2. Inputs:
   - `tc_id` = `Var_TCID`
   - `phase_num` = `Var_PhaseNum` (as text — use expression `string(Topic.Var_PhaseNum)`)
   - `decision` = `APPROVED` (type literal)
   - `reason` = `Var_Reason`
3. Output: `result` → `Var_Result`

### 9.6 Message

```
✅ {Var_Result}

The pipeline will advance to Phase {Var_PhaseNum + 1} automatically.
```

### 9.7 Quick replies

`Run Next Phase` | `Check Status` | `Main Menu`

---

## PHASE 10 — Topic T5: Reject Phase (15 min)

### 10.1 Create topic

1. Name: `Reject Phase`
2. Trigger phrases:
   - `reject phase` | `send back` | `not approved` | `needs rework` | `fail phase`

### 10.2 Collect inputs

1. `Which ticket?` → `Var_TCID`
2. `Which phase number? (1–8)` → `Var_PhaseNum`
3. `Please provide the rejection reason (required — this is sent to the development team):` → `Var_Reason`

### 10.3 Confirmation step

Same pattern as T4 step 9.3:
- Text: `Confirm: Reject **{Var_TCID}** Phase **{Var_PhaseNum}**?`
- Options: `Yes, reject` | `No, cancel`
- Save as: `Var_Confirm`

### 10.4 Condition + call F4

Same structure as T4 steps 9.4–9.5, but pass:
- `decision` = `REJECTED` (literal)
- `reason` = `Var_Reason`

### 10.5 Message

```
❌ {Var_TCID} Phase {Var_PhaseNum} has been REJECTED.
Reason recorded: {Var_Reason}

The agent team will be notified to re-run this phase.
```

---

## PHASE 11 — Topic T1: Create & Run Feature Pipeline (20 min)

### 11.1 Create topic

1. Name: `Create Feature Request`
2. Trigger phrases:
   - `new feature` | `create ticket` | `start pipeline`
   - `add requirement` | `new user story` | `run pipeline`

### 11.2 Question — user story

1. + node → **Ask a question**
2. Text:
```
Please describe the feature as a user story:
(e.g. "As a developer, I want X so that Y")
```
3. Identify: User's entire response
4. Variable: `Var_UserStory`

### 11.3 Confirmation

1. Message: `I'll create a new pipeline ticket for: "{Var_UserStory}"`
2. Ask question → `Confirm?` → options: `Yes, create it` | `No, let me rephrase`
3. Condition: if No → redirect to step 11.2 (use **Go to another step** → point to the user story question)

### 11.4 Call F1 (initialize)

1. Call an action → `DocSync - Initialize Pipeline`
2. Input: `user_story` = `Var_UserStory`
3. Outputs: `tc_id` → `Var_NewTCID`, `message` → `Var_InitMessage`

### 11.5 Ask whether to run phase 1 now

1. + node → **Ask a question**
2. Text: `Ticket **{Var_NewTCID}** created! Would you like to run Phase 1 (Requirements) now?`
3. Options: `Yes, run now` | `No, I'll trigger it later`
4. Save as: `Var_RunNow`

### 11.6 Condition — run phase 1

**Yes branch:**
1. Call an action → `DocSync - Trigger Pipeline Phase`
2. Inputs:
   - `tc_id` = `Var_NewTCID`
   - `phase` = `1` (literal)
   - `user_story` = `Var_UserStory`
   - `from_phase` = (blank)
3. Output: `status` → `Var_RunStatus`, `log_tail` → `Var_LogTail`

4. Message:
```
🚀 Phase 1 (Requirements) is running for **{Var_NewTCID}**.

Container status: {Var_RunStatus}

Use "check status {Var_NewTCID}" to see results and approve when ready.
```

**No branch:**
Message:
```
✅ Ticket **{Var_NewTCID}** initialized.

Use "start pipeline {Var_NewTCID}" when ready to run Phase 1.
```

---

## PHASE 12 — Topic T6: List All Tickets (10 min)

### 12.1 Create topic

1. Name: `List All Tickets`
2. Trigger phrases:
   - `show all tickets` | `list tickets` | `what's in progress`
   - `active pipelines` | `all TCs` | `overview`

### 12.2 Call F5 directly

1. + node → **Call an action** → `DocSync - List All Tickets`
2. No inputs needed
3. Outputs: `active_tcs` → `Var_ActiveTCs`

### 12.3 Message

```
📊 **Active Tickets:**
{Var_ActiveTCs}

Type "check status TC-XXX" for details on any ticket.
```

---

## PHASE 13 — Publish to Teams (10 min)

### 13.1 Publish the copilot

1. Copilot Studio → click **Publish** (top right) → **Publish**
2. Wait ~2 minutes

### 13.2 Add to Microsoft Teams

1. Settings → Channels → Microsoft Teams → **Turn on Teams**
2. Click **Open the bot in Teams**
3. Teams opens → click **Add** → the bot appears in your chat list

### 13.3 Test end-to-end in Teams

Type these in order to verify the full flow:

```
show all tickets
→ should list TC-001 through TC-004

check status TC-002
→ should return COMPLETE, Phase 8

new feature
→ enter a user story → confirm → choose "Yes, run now"
→ flow starts ACI container (~3 min) → returns Succeeded
```

---

## Build Checklist

```
PHASE 0   ✓ GitHub fine-grained PAT created (Contents read+write)
          ✓ Docker image built and pushed to docsyncreg.azurecr.io
          ✓ 9 Power Platform Environment Variables created

FLOWS     ✓ F1  DocSync - Initialize Pipeline
          ✓ F2  DocSync - Get Ticket Status
          ✓ F3  DocSync - Get Phase Output
          ✓ F5  DocSync - List All Tickets
          ✓ F4  DocSync - Record Phase Decision
          ✓ FA  DocSync - Trigger Pipeline Phase

COPILOT   ✓ Copilot created — DocSync Pipeline Assistant
          ✓ Greeting topic updated

TOPICS    ✓ T2  Check Ticket Status
          ✓ T3  Review Phase Output
          ✓ T4  Approve Phase
          ✓ T5  Reject Phase
          ✓ T1  Create Feature Request
          ✓ T6  List All Tickets

PUBLISH   ✓ Published to Teams channel
          ✓ End-to-end test passed (list → status → create → approve)
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| F2 returns 404 | `docsync_github_repo` value wrong | Check `owner/repo` format, no trailing slash |
| F2 returns 401 | PAT expired or wrong scope | Regenerate — needs Contents: read+write |
| F2 returns 422 | File doesn't exist yet | Run init pipeline first for that TC |
| FA container exits immediately | Missing env var | Check container logs in step 5.7 |
| FA status stays `Running` forever | Container hung | Check `ANTHROPIC_API_KEY` is valid |
| F4 PUT returns 409 Conflict | SHA mismatch | Re-run F2 to get fresh SHA before F4 |
| Copilot action not listed | Flow not saved | Save + re-open the topic action picker |
| ACI connector not visible | Azure connection not set up | Add the connection in step 5.4 — sign in to Azure |
