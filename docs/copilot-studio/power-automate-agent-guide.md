# Power Automate Agent — Step-by-Step Build Guide

DocSync SDLC — Create Agent with GitHub + Confluence Tools

Total estimated time: ~2.5 hours
Build order: Connections → Agent → Tools → Flows → Test

> **License note:** Power Automate Agents require a **Power Automate Premium** license
> or **Microsoft 365 Copilot** license. Verify before starting at
> https://make.powerautomate.com → top-right account → View my licenses.

---

## PART 1 — Create Connections First (20 min)

Connections are reusable authenticated links to external services.
Create them once, then every flow and agent shares them.

### 1.1 Create GitHub Connection

1. Go to https://make.powerautomate.com
2. Left sidebar → **Data** → **Connections**
3. Click **+ New connection**
4. Search: `GitHub` → select **GitHub**
5. Click **Create**
6. A browser popup appears → **Authorize Power Automate** to access GitHub
7. Sign in with your GitHub account → click **Authorize**
8. Connection appears in your list as `GitHub — yourname@email.com`

### 1.2 Create Confluence Connection

1. **+ New connection** → search `Confluence`
2. If **Confluence Cloud** appears in the list:
   - Select it → enter:
     - Instance URL: `https://epam-team-wp8j4x2l.atlassian.net`
     - Username: your Atlassian email
     - API Token: your Atlassian API token
   - Click **Create**

3. If Confluence does not appear (it is not always in the standard catalog):
   - Use **HTTP with Azure AD** or the plain **HTTP** connector instead
   - The flows in Part 3 will show both options

### 1.3 Create HTTP Connection (for Anthropic / custom calls)

The HTTP connector needs no pre-created connection — it authenticates per action.
Skip this step; it is configured inside each flow.

---

## PART 2 — Create the Agent (15 min)

### 2.1 Open the Agents section

1. Left sidebar → **Agents** (under Create, or direct link: make.powerautomate.com/agents)
2. Click **+ New agent**

> If you do not see Agents in the sidebar, your environment may need it enabled.
> Go to Admin Center → Environments → your environment → Settings → Features → enable **AI agents**.

### 2.2 Name and describe the agent

1. **Name**: `DocSync SDLC Agent`
2. **Description**:
   ```
   Manages the DocSync SDLC pipeline for the PO/BA team.
   Can check ticket status, retrieve phase outputs, approve or reject phases,
   create new feature tickets, list active tickets, and trigger pipeline runs.
   ```
3. Click **Next** or **Create**

### 2.3 Write the agent instructions

In the **Instructions** box, paste:

```
You are the DocSync SDLC Pipeline Assistant for the PO/BA team.

You help product owners and business analysts manage an 8-phase software
development pipeline. The pipeline phases are:
  1 = Requirements
  2 = Architecture
  3 = Design Review
  4 = Implementation Planning
  5 = Implementation
  6 = Code Review
  7 = Verification
  8 = PR Creation

Ticket IDs follow the format TC-001, TC-002, etc.
The GitHub repository is stored in your tools.
Phase status is tracked in outputs/{TC-ID}/phase-status.json in the repo.
Phase outputs are in outputs/{TC-ID}/{phase-folder}/output.md.

When a user asks to check status — use the Get Ticket Status tool.
When a user asks to see a phase output — use the Get Phase Output tool.
When a user approves a phase — use the Record Approval tool.
When a user rejects a phase — use the Record Rejection tool with a reason.
When a user wants a new feature ticket — use the Initialize Pipeline tool.
When a user wants to run a phase — use the Trigger Phase tool.
When a user asks to list all tickets — use the List All Tickets tool.

Always confirm before writing any changes. Show the TC-ID and phase clearly.
```

4. Click **Save**

---

## PART 3 — Add Tools to the Agent (30 min)

Tools are either connectors (direct API calls) or flows (multi-step logic).
Add them one by one from the agent's Tools tab.

### 3.1 Open the Tools panel

1. Inside your agent → click **Tools** tab (or **+ Add tool**)

---

### Tool 1 — GitHub: Get File Content

This tool reads any file from the repo (used for status and output files).

1. Click **+ Add tool** → **From connector**
2. Search: `GitHub` → select the GitHub connector
3. Find action: **Get file content** (or **Get contents**)
4. Select it → click **Add**
5. Connection: select the GitHub connection created in Part 1
6. **Tool display name**: `Get GitHub File`
7. **Description** (the agent reads this to decide when to call it):
   ```
   Reads the content of any file from the GitHub repository.
   Use this to get phase-status.json or output.md files.
   Inputs: owner (repo owner), repo (repo name), path (file path like outputs/TC-004/phase-status.json)
   ```
8. Click **Save tool**

---

### Tool 2 — GitHub: Create or Update File

This tool writes files back to the repo (used for approvals and status updates).

1. **+ Add tool** → **From connector** → **GitHub**
2. Find action: **Create or update file contents**
3. Add tool → Connection: same GitHub connection
4. **Tool display name**: `Write GitHub File`
5. **Description**:
   ```
   Creates or updates a file in the GitHub repository.
   Use this to write approval.json or update phase-status.json.
   Requires: owner, repo, path, message (commit message), content (base64-encoded), sha (if updating existing file), branch.
   ```
6. Click **Save tool**

---

### Tool 3 — GitHub: List Repository Contents

Lists files and folders at a path — used to check what TC folders exist.

1. **+ Add tool** → **From connector** → **GitHub**
2. Find action: **List repository contents** (or **Get contents** with a folder path)
3. **Tool display name**: `List GitHub Folder`
4. **Description**:
   ```
   Lists the contents of a folder in the GitHub repository.
   Use this to list all TC folders under outputs/ to find active tickets.
   Input: path = outputs
   ```
5. **Save tool**

---

### Tool 4 — Confluence: Get Page (native connector)

**If you created a Confluence connection in step 1.2:**

1. **+ Add tool** → **From connector** → **Confluence Cloud**
2. Find action: **Get page by ID** or **Get content**
3. **Tool display name**: `Get Confluence Page`
4. **Description**:
   ```
   Retrieves a Confluence page by its ID.
   Use this to check if a SDLC doc has already been published.
   ```
5. **Save tool**

---

### Tool 4 (alternative) — Confluence: HTTP action

**If Confluence connector is not available:**

1. **+ Add tool** → **From flow** → create a new flow (see Part 4, Flow FC)
2. Wire the HTTP call to Confluence API inside the flow
3. Add the flow as the tool (instructions in Part 4 below)

---

### Tool 5 — Confluence: Create or Update Page (flow-based)

Since creating a Confluence page from an agent requires more logic
(check if page exists, create or update accordingly), this is best wrapped in a flow.

See **Part 4, Flow FC** → then add that flow here as a tool.

---

### Tool 6 — Flow: Initialize Pipeline

Add the flow you will build in Part 4 (Flow F1) as a tool.

1. **+ Add tool** → **From flow** → select `DocSync - Initialize Pipeline`
2. **Tool display name**: `Initialize Pipeline`
3. **Description**:
   ```
   Creates a new SDLC pipeline ticket in the GitHub repo.
   Automatically assigns the next TC-ID and creates the folder structure.
   Input: user_story — the feature description as a user story.
   Returns: tc_id (e.g. TC-006), message.
   ```
4. **Save tool**

Repeat this step for each flow in Part 4:
- `DocSync - Trigger Pipeline Phase` → tool name: `Trigger Phase`
- `DocSync - Get Ticket Status` → tool name: `Get Ticket Status`
- `DocSync - Get Phase Output` → tool name: `Get Phase Output`
- `DocSync - Record Phase Decision` → tool name: `Record Phase Decision`
- `DocSync - List All Tickets` → tool name: `List All Tickets`
- `DocSync - Publish to Confluence` → tool name: `Publish to Confluence`

---

## PART 4 — Create the Flows (60 min)

These flows contain the multi-step logic. The agent calls them as tools.
Build them in Power Automate → Create → Instant cloud flow → trigger: **Run a flow from Copilot** or **Manually trigger a flow**.

> Use **Run a flow from Copilot** as the trigger so the agent can call them directly.

---

### Flow F1 — Initialize Pipeline

**Purpose**: Creates `outputs/TC-XXX/phase-status.json` and 8 phase `.gitkeep` files in GitHub.

**Trigger inputs**:
- `user_story` (Text)

**Steps**:

```
1. GitHub: Get file content
   Owner: {your GitHub username}
   Repo:  {your repo name}
   Path:  outputs/phase-status.json
   → Rename: Get_Master_Status

2. Compose — Decode master JSON
   Expression: base64ToString(body('Get_Master_Status')?['content'])
   → Rename: Decode_Master

3. Compose — Count existing TCs
   Expression: length(json(outputs('Decode_Master'))?['active_test_cases'])
   → Rename: TC_Count

4. Compose — Build new TC ID
   Expression:
     concat('TC-0',string(add(outputs('TC_Count'),1)))
   → Rename: New_TC_ID
   ▎ For TC-010+ add proper padding logic; this covers TC-001 to TC-009

5. Compose — Build phase-status.json content
   (paste the JSON template from build-guide.md Phase 5, step 5.3
    replacing static TC-IDs with @{outputs('New_TC_ID')} expressions)
   → Rename: Build_TC_Status

6. GitHub: Create or update file contents
   Owner: {your owner}
   Repo:  {your repo}
   Path:  outputs/@{outputs('New_TC_ID')}/phase-status.json
   Message: chore: init @{outputs('New_TC_ID')} [skip ci]
   Content: @{base64(outputs('Build_TC_Status'))}
   Branch: main
   → Rename: Write_Status_File

7. Apply to each — Create 8 phase .gitkeep files
   Input array expression:
     array(['phase-1-requirements','phase-2-architecture','phase-3-design-review',
            'phase-4-impl-planning','phase-5-implementation','phase-6-code-review',
            'phase-7-verification','phase-8-pr'])
   Inside loop:
     GitHub: Create or update file contents
       Path: outputs/@{outputs('New_TC_ID')}/@{items('Apply_to_each')}/.gitkeep
       Message: chore: create folder @{items('Apply_to_each')} [skip ci]
       Content: Cg==   ← base64 of newline character
       Branch: main

8. Respond to Copilot / Return values
   tc_id   = @{outputs('New_TC_ID')}
   message = Pipeline initialized. Ticket ID: @{outputs('New_TC_ID')}
```

---

### Flow F2 — Get Ticket Status

**Trigger inputs**: `tc_id` (Text)

```
1. GitHub: Get file content
   Path: outputs/@{triggerBody()['text']}/phase-status.json
   → Rename: Get_Status_File

2. Compose — Decode
   Expression: base64ToString(body('Get_Status_File')?['content'])
   → Rename: Decode_Status

3. Parse JSON on Decode_Status output (schema: same as build-guide.md Phase 1 step 1.6)

4. Respond to Copilot
   pipeline_status = from Parse JSON
   current_phase   = from Parse JSON
   user_story      = from Parse JSON
   full_json       = Outputs from Decode_Status
   sha             = @{body('Get_Status_File')?['sha']}
```

---

### Flow F3 — Get Phase Output

**Trigger inputs**: `tc_id` (Text), `phase_num` (Text)

```
1. Compose — Get folder name
   Expression: array([...])[sub(int(triggerBody()['text_1']),1)]
   (same folder array as build-guide.md)

2. GitHub: Get file content
   Path: outputs/@{triggerBody()['text']}/@{outputs('Get_Folder_Name')}/output.md

3. Compose — Decode + truncate
   Expression: substring(base64ToString(body('Get_file_content')?['content']),0,3000)

4. Respond to Copilot
   output_markdown = Decode output
   phase_folder    = Get_Folder_Name output
```

---

### Flow F4 — Record Phase Decision

**Trigger inputs**: `tc_id`, `phase_num`, `decision`, `reason`

```
1. Compose — Get_Folder_Name (array lookup, same as above)
2. Compose — Get_Phase_Name  (name array lookup)
3. Compose — Get_Timestamp: utcNow('yyyy-MM-ddTHH:mm:ssZ')

4. GitHub: Get file content — approval.json (to get SHA if exists)
   Path: outputs/@{triggerBody()['text']}/@{outputs('Get_Folder_Name')}/approval.json
   Set "Suppress HTTP errors": Yes
   → Rename: Get_Approval_SHA

5. Condition — statusCode equals 200
   Yes: Compose Extract_SHA = body('Get_Approval_SHA')?['sha']
   No:  Compose Extract_SHA = '' (empty)

6. Compose — Build_Approval_JSON
   (concat expression building the JSON string — see build-guide.md Phase 4 step 4.7)

7. GitHub: Create or update file contents — write approval.json
   Path: outputs/{tc_id}/{folder}/approval.json
   Content: @{base64(outputs('Build_Approval_JSON'))}
   SHA: @{outputs('Extract_SHA')}

8. GitHub: Get file content — phase-status.json (to get current SHA)
9. Compose — Decode_Phase_Status
10. Compose — Build_Updated_Status (string replace on status field)
11. GitHub: Create or update file contents — write phase-status.json

12. Respond to Copilot
    result = @{triggerBody()['text']} Phase @{triggerBody()['text_1']} recorded as @{triggerBody()['text_2']}
```

---

### Flow F5 — List All Tickets

**Trigger**: no inputs

```
1. GitHub: Get file content
   Path: outputs/phase-status.json

2. Compose — Decode: base64ToString(...)

3. Parse JSON — extract active_test_cases array

4. Compose — Format: join(body('Parse_JSON')?['active_test_cases'], ' | ')

5. Respond to Copilot
   active_tcs  = Format output
   master_json = Decode output
```

---

### Flow FA — Trigger Pipeline Phase (ACI)

**Trigger inputs**: `tc_id`, `phase`, `user_story`, `from_phase`

This flow starts an Azure Container Instance that runs Claude Code.
Full step-by-step is in `build-guide.md` Part 5 (PHASE 5).

Key steps summary:
```
1. Get all 9 Environment Variables (see build-guide.md reusable pattern)
2. Compose — Container_Group_Name (unique name)
3. Azure Container Instance — Create or update container group
   (all env vars passed in, image from ACR)
4. Delay 30 seconds
5. Do Until — poll Get container group until state != Running
   (60-second delay inside loop)
6. Azure Container Instance — List logs
7. Azure Container Instance — Delete container group
8. Respond to Copilot: status + log_tail
```

---

### Flow FC — Publish to Confluence

**Trigger inputs**: `tc_id`, `page_title`, `content_markdown`

```
1. HTTP — Check if page exists
   Method: GET
   URI: https://epam-team-wp8j4x2l.atlassian.net/wiki/rest/api/content?spaceKey=DOCS&title=@{triggerBody()['text_1']}
   Headers:
     Authorization: Basic @{base64(concat('your@email.com',':','YOUR_CONFLUENCE_TOKEN'))}
     Accept: application/json
   ▎ Replace email and token with Power Platform Environment Variable references

2. Condition — results size > 0
   Yes (update existing page):
     Compose: page_id = body('HTTP')?['results']?[0]?['id']
     HTTP — PUT to update page
       URI: https://epam-team-wp8j4x2l.atlassian.net/wiki/rest/api/content/@{outputs('page_id')}
       Body: { "version": {"number": incremented}, "title": ..., "body": {...} }

   No (create new page):
     HTTP — POST to create page
       URI: https://epam-team-wp8j4x2l.atlassian.net/wiki/rest/api/content
       Body:
         {
           "type": "page",
           "title": "@{triggerBody()['text_1']}",
           "space": { "key": "DOCS" },
           "ancestors": [{ "id": "123456" }],
           "body": {
             "storage": {
               "value": "@{triggerBody()['text_2']}",
               "representation": "storage"
             }
           }
         }

3. Respond to Copilot
   page_url = @{body('HTTP')?['_links']?['base']}@{body('HTTP')?['_links']?['webui']}
   message  = Page published: @{triggerBody()['text_1']}
```

---

## PART 5 — Wire All Flows as Agent Tools (15 min)

After all flows are saved and tested:

1. Go back to your `DocSync SDLC Agent` → **Tools** tab
2. For each flow, click **+ Add tool** → **From flow** → select the flow
3. Add the description from the table below

| Flow name | Tool name | When agent uses it |
|---|---|---|
| DocSync - Initialize Pipeline | `Initialize Pipeline` | User requests new feature/ticket |
| DocSync - Trigger Pipeline Phase | `Trigger Phase` | User wants to run a phase |
| DocSync - Get Ticket Status | `Get Ticket Status` | User asks about status |
| DocSync - Get Phase Output | `Get Phase Output` | User wants to review a phase |
| DocSync - Record Phase Decision | `Record Phase Decision` | User approves or rejects |
| DocSync - List All Tickets | `List All Tickets` | User asks for overview |
| DocSync - Publish to Confluence | `Publish to Confluence` | User wants to publish SDLC docs |

For the GitHub connector tools added directly (Tool 1–3 in Part 3), the agent can call them
for raw file reads — useful as a fallback when flows are not needed.

---

## PART 6 — Configure Knowledge (optional, 10 min)

Add knowledge sources so the agent understands your project without asking:

1. Agent → **Knowledge** tab → **+ Add knowledge**
2. Options:
   - **File** → upload `docs/TC-005/requirements.md` as context
   - **URL** → paste your Confluence space URL
   - **Dataverse table** → if you store TC metadata in Dataverse

This lets the agent answer questions like "what is TC-005 about?" without calling GitHub.

---

## PART 7 — Test the Agent (15 min)

### 7.1 Test inside Power Automate

1. Agent → **Test** tab (top right panel)
2. Type each prompt and verify the response:

```
show all tickets
→ agent calls List All Tickets flow → returns TC-001 | TC-002 | ...

check status TC-002
→ agent calls Get Ticket Status → returns pipeline status and phase

show phase 1 output for TC-002
→ agent calls Get Phase Output → returns requirements markdown

approve TC-002 phase 1
→ agent asks for confirmation → calls Record Phase Decision → returns confirmation

new feature: As a developer, I want automatic retries on failed syncs
→ agent calls Initialize Pipeline → returns TC-006 created
→ agent asks if you want to run phase 1 now
→ if yes → calls Trigger Phase → ACI starts → returns Succeeded
```

### 7.2 Connect to Copilot Studio (optional)

If you want a chat UI in Teams, connect this agent to Copilot Studio:

1. Copilot Studio → Create → New copilot → **Use an existing agent**
2. Select your `DocSync SDLC Agent` from Power Automate
3. Publish → Teams

OR use the agent directly from Power Automate's built-in chat interface
without needing Copilot Studio at all.

---

## PART 8 — Add Agent to Teams Directly (10 min)

Power Automate agents can be added to Teams without Copilot Studio:

1. Agent → **Channels** tab → **Microsoft Teams**
2. Click **Add to Teams**
3. Teams opens → click **Add**
4. The agent appears in your Teams chat list as `DocSync SDLC Agent`

---

## Summary — What you built

```
Agent: DocSync SDLC Agent (Power Automate)
  │
  ├── Tools from GitHub connector (direct)
  │     ├── Get GitHub File        (read any file from repo)
  │     ├── Write GitHub File      (write any file to repo)
  │     └── List GitHub Folder     (list TC folders)
  │
  ├── Tools from flows
  │     ├── Initialize Pipeline    (F1 — creates TC folder + status JSON)
  │     ├── Trigger Phase          (FA — starts ACI container with Claude Code)
  │     ├── Get Ticket Status      (F2 — reads phase-status.json)
  │     ├── Get Phase Output       (F3 — reads output.md)
  │     ├── Record Phase Decision  (F4 — writes approval + updates status)
  │     ├── List All Tickets       (F5 — reads master status)
  │     └── Publish to Confluence  (FC — creates/updates Confluence pages)
  │
  └── Knowledge (optional)
        ├── Confluence space URL
        └── Uploaded SDLC docs
```

---

## Build Checklist

```
PART 1    ✓ GitHub connection created (OAuth)
          ✓ Confluence connection created (or HTTP confirmed)

PART 2    ✓ Agent created — DocSync SDLC Agent
          ✓ Instructions pasted

PART 3    ✓ Tool 1 — Get GitHub File (connector)
          ✓ Tool 2 — Write GitHub File (connector)
          ✓ Tool 3 — List GitHub Folder (connector)
          ✓ Tool 4 — Get/Create Confluence Page

PART 4    ✓ F1 — Initialize Pipeline (tested)
          ✓ F2 — Get Ticket Status (tested)
          ✓ F3 — Get Phase Output (tested)
          ✓ F4 — Record Phase Decision (tested)
          ✓ F5 — List All Tickets (tested)
          ✓ FA — Trigger Pipeline Phase (tested)
          ✓ FC — Publish to Confluence (tested)

PART 5    ✓ All 7 flows added as agent tools with descriptions

PART 6    ✓ Knowledge sources added (optional)

PART 7    ✓ Agent tested in Power Automate test panel
          ✓ All 5 test prompts verified

PART 8    ✓ Agent added to Microsoft Teams
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| GitHub connector not authorizing | Pop-up blocked | Allow pop-ups for make.powerautomate.com |
| GitHub action returns 404 | Wrong owner or repo name | Check owner = GitHub username, repo = exact repo name |
| GitHub write returns 422 | SHA missing on update | Add Get file step before write to fetch current SHA |
| Confluence HTTP 401 | Wrong token format | Use `Basic base64(email:token)` — not Bearer |
| Agent does not call the right tool | Tool description too vague | Rewrite description with explicit trigger keywords |
| Flow not appearing in agent tools | Flow not saved or wrong trigger | Save flow, confirm trigger is "Run a flow from Copilot" |
| ACI container times out | Claude Code taking too long | Increase Do Until limit to 120 iterations, or set PHASE=1 not full |
