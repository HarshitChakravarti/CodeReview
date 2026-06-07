# CodeReview Agent — AI Coding Assistant Prompt

> Paste this entire prompt to your AI coding assistant to start building. Update the "Current Status" section as you complete each phase.

---

## Project Context

You are helping me build a **multi-agent GitHub PR review system** called **CodeReview Agent**. This is a portfolio project for my resume as an AI/ML engineer. I am a second-year B.Tech CSE (AI & ML) student at VIT Bhopal, comfortable with Python and React/Next.js but completely new to LangChain and LangGraph.

The system works like this: when a developer opens a GitHub Pull Request, my system automatically clones the repo, runs a security scanner agent and a logic reviewer agent in parallel, executes the test suite inside a Docker sandbox, synthesises all findings into a markdown review, pauses for my approval via a web dashboard, and then posts the approved review as a GitHub PR comment.

---

## Tech Stack

- **LLM:** Gemini 2.5 Flash via Google AI Studio (`langchain-google-genai`)
- **Agent orchestration:** LangGraph (I am learning this as I build)
- **LLM framework:** LangChain
- **Backend:** FastAPI + uvicorn
- **Sandboxing:** Docker (Python SDK, not CLI)
- **GitHub integration:** PyGithub + gitpython
- **Frontend:** Next.js + Tailwind + shadcn/ui
- **State persistence:** SQLite via LangGraph's `SqliteSaver` checkpointer

---

## Completed Prerequisites

- [x] Virtual environment created and activated
- [x] All packages installed: `langgraph`, `langchain`, `langchain-google-genai`, `langchain-community`, `gitpython`, `pygithub`, `fastapi`, `uvicorn`, `python-dotenv`, `docker`, `tenacity`, `rich`
- [x] `.env` file created with `GOOGLE_API_KEY`, `GITHUB_TOKEN`, `GITHUB_WEBHOOK_SECRET`
- [x] Docker Desktop installed and verified (`docker run --rm hello-world` passes)
- [x] ARM-native image pulled: `docker pull --platform linux/arm64 python:3.11-slim`
- [x] Hello World 1 passes: Gemini responds via `ChatGoogleGenerativeAI`
- [x] Hello World 2 passes: Minimal LangGraph runs and returns updated state
- [x] Project folder structure created (empty files in place)

---

## Project Folder Structure

```
codereview-agent/
├── agents/
│   ├── diff_reader.py
│   ├── security_scanner.py
│   ├── logic_reviewer.py
│   ├── test_runner.py
│   └── review_writer.py
├── graph/
│   ├── state.py
│   └── graph.py
├── api/
│   └── main.py
├── dashboard/           ← Next.js app (Phase 6)
├── .env
├── .gitignore
└── requirements.txt
```

---

## How I Want You to Help Me

**Teaching style:** I am learning LangGraph as I build this. Do not just give me code to copy-paste. For every non-trivial piece of code you write:
1. Write the code
2. Add a short comment above each logical block explaining *why* it works that way, not just *what* it does

**Testing approach:** After every node or function we build, remind me to test it in isolation before connecting it to the graph. Tell me exactly what to pass in and what I should see in the output.

**Errors:** If I paste an error, help me understand what caused it, not just how to fix it.

**One phase at a time:** Only move to the next phase when I confirm the checkpoint of the current phase passes.

---

## Current Status

> **Update this section each time you start a new session or complete a phase.**

- **Phase currently working on:** Phase 4 — Review Writer + Human-in-the-Loop
- **Last completed checkpoint:** Phase 3 completed. Docker sandbox implemented and passing tests with `network_mode="bridge"` to allow dynamic dependency installation. 
- **Next checkpoint to hit:** Graph pauses at interrupt, resumes on Command, review appears on GitHub PR.

---

## Full Implementation Plan (For Your Reference)

### Phase 1 — State Definition & Diff Reader Agent (Days 4–7)

**Step 1.1 — graph/state.py**

Define `ReviewState` as a Python `TypedDict`. Fields needed:

*Inputs (set at graph startup):*
- `repo_url: str`
- `pr_number: int`
- `base_sha: str`
- `head_sha: str`

*Set by diff reader:*
- `repo_path: str`
- `raw_diff: str`
- `file_diffs: List[dict]` — list of `{"filename": str, "diff": str}`

*Set by parallel agents (critical — must use `Annotated[List[Finding], operator.add]` merge strategy or parallel agents will overwrite each other):*
- `findings: Annotated[List[Finding], operator.add]`

*Set by test runner:*
- `test_results: str`

*Set by review writer:*
- `draft_review: str`

*Set by human approval:*
- `action: str` — `"approve"` or `"reject"`
- `human_comment: str`

Also define a `Finding` dataclass with: `file: str`, `line: int`, `severity: str`, `category: str`, `description: str`

**Step 1.2 — agents/diff_reader.py**

Function: `diff_reader_node(state: dict) -> dict`

Logic:
1. Use `tempfile.mkdtemp()` to create a throwaway directory
2. Clone the repo using `git.Repo.clone_from(state["repo_url"], tmp_dir)`
3. Extract the diff using `repo.git.diff(state["base_sha"], state["head_sha"])`
4. Write a helper `parse_diff_by_file(raw_diff: str) -> List[dict]` that splits on `"diff --git"` lines and returns one dict per file
5. Return `{"repo_path": tmp_dir, "raw_diff": raw_diff, "file_diffs": file_chunks}`

Checkpoint: Call `diff_reader_node({...})` standalone with a real public GitHub repo URL and two real commit SHAs. Print the result. Expect a list of dicts with `filename` and `diff` keys.

---

### Phase 2 — Parallel Security & Logic Agents (Days 8–13)

**Key concept:** Use `Send()` for fan-out. Declare `findings` with `Annotated[List[Finding], operator.add]` so parallel results merge instead of overwrite.

**Step 2.1 — agents/security_scanner.py**

Function: `security_scanner_node(state: dict) -> dict`

- LLM: `ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)`
- System prompt: instruct Gemini to find hardcoded secrets, SQL injection, dangerous functions (`eval`, `exec`, `pickle.loads`), missing input validation, insecure dependencies
- Output format: JSON array only, each item `{"file": str, "line": int, "severity": "critical"|"warning"|"info", "description": str}`. Empty array if no issues.
- Loop over `state["file_diffs"]`, trim each diff to 3000 chars, send to Gemini, parse JSON, convert to `Finding` objects with `category="security"`
- Wrap JSON parsing in try/except — never crash the graph
- Wrap `.invoke()` with `@retry` from `tenacity` (3 attempts, exponential backoff)
- Return `{"findings": list_of_findings}`

**Step 2.2 — agents/logic_reviewer.py**

Identical structure to security scanner. Different system prompt: find functions that are too long, missing error handling, logic bugs, dead code, poor naming. Set `category="logic"`.

**Step 2.3 — graph/graph.py (partial)**

- Create `StateGraph(ReviewState)`
- Add nodes: `diff_reader`, `security_scanner`, `logic_reviewer`
- Connect `START → diff_reader`
- Write routing function returning `[Send("security_scanner", state), Send("logic_reviewer", state)]`
- Connect via `add_conditional_edges("diff_reader", routing_fn)`
- Temporarily connect both agents to `END`
- Compile and test with dummy `file_diffs`

Checkpoint: `state["findings"]` contains results from both agents merged into one list.

---

### Phase 3 — Docker Sandboxed Test Runner (Days 14–18)

**Step 3.1 — agents/test_runner.py**

Function: `test_runner_node(state: dict) -> dict`

- Connect to Docker: `docker.from_env()`
- Run container with:
  - Image: `python:3.11-slim`, platform: `linux/arm64`
  - Command: `bash -c 'pip install -r requirements.txt -q && pytest --tb=short -q'`
  - Volume: `state["repo_path"]` mounted to `/code` as read-only
  - Working dir: `/code`
  - `mem_limit="512m"`, `cpu_period=100000`, `cpu_quota=50000`
  - `network_mode="none"` — no internet
  - `remove=True`, `stdout=True`, `stderr=True`
- Decode output bytes to string
- Wrap everything in try/except — on failure set `test_results` to the error message string
- Return `{"test_results": output}`

Checkpoint: Point at a local Python repo with tests. `test_runner_node()` returns pytest output. Confirm network mode none — container cannot ping the internet.

---

### Phase 4 — Review Writer + Human-in-the-Loop (Days 19–24)

**Step 4.1 — agents/review_writer.py**

Function: `review_writer_node(state: dict) -> dict`

- Format `state["findings"]` sorted by severity (critical first) into a text block
- System prompt: senior engineer writing a GitHub PR review in GitHub-flavored markdown. Sections: Summary, Critical Issues `[CRITICAL]`, Warnings `[WARN]`, Suggestions `[INFO]`, Test Results
- Use `temperature=0.2` for more natural prose
- Return `{"draft_review": response.content}`

**Step 4.2 — graph/graph.py — human_approval_node**

- Call `interrupt({"draft_review": state["draft_review"], "pr_number": state["pr_number"], "findings_count": len(state["findings"])})`
- After interrupt returns: read `decision["approved"]`, write `action` and `human_comment` to state
- Return `{"action": ..., "human_comment": ...}`

**Step 4.3 — graph/graph.py — post_to_github_node**

- If `state["action"] != "approve"`: return immediately
- Use `PyGithub` to get the repo and PR, call `pr.create_review(body=state["draft_review"], event="COMMENT")`

**Step 4.4 — graph/graph.py — add checkpointer**

- `SqliteSaver.from_conn_string("reviews.db")`
- Pass to `builder.compile(checkpointer=checkpointer)`
- Add remaining edges: `test_runner → review_writer → human_approval → post_to_github → END`
- Remove temporary END connections from Phase 2

- Invoke with `config = {"configurable": {"thread_id": str(uuid.uuid4())}}`
- After interrupt pauses, manually resume with `Command(resume={"approved": True})`

Checkpoint: Graph pauses at interrupt, resumes on Command, review appears on GitHub PR.

---

### Phase 5 — FastAPI Webhook Server (Days 25–27)

**Step 5.1 — api/main.py**

Endpoints needed:

`POST /webhook/github`
- Read raw body, verify HMAC-SHA256 signature against `X-Hub-Signature-256` header using `GITHUB_WEBHOOK_SECRET`
- Return 403 if invalid
- Only process actions `"opened"` and `"synchronize"`
- Extract: `repo_url`, `pr_number`, `base_sha`, `head_sha`
- Generate `thread_id = str(uuid.uuid4())`
- Add background task to run the graph
- Return `{"status": "review started", "thread_id": thread_id}` immediately

`GET /reviews/pending`
- Return list of `{"thread_id": ..., "data": interrupt_payload}` from in-memory dict

`POST /reviews/{thread_id}/approve`
- Call `graph.invoke(Command(resume={"approved": True, "comment": body.comment}), config=...)`
- Remove from pending dict

`POST /reviews/{thread_id}/reject`
- Call `graph.invoke(Command(resume={"approved": False}), config=...)`
- Remove from pending dict

Also add `CORSMiddleware` allowing `http://localhost:3000`.

**Step 5.2 — ngrok setup**

- `brew install ngrok`, `ngrok http 8000`
- Set webhook URL in GitHub repo settings to `https://<ngrok-url>/webhook/github`
- Events: Pull requests only

Checkpoint: Open a test PR → webhook fires → graph starts in background → `/reviews/pending` returns the review.

---

### Phase 6 — Next.js Dashboard (Days 28–32)

**Setup:**
- `npx create-next-app@latest dashboard --typescript --tailwind --app`
- `cd dashboard && npx shadcn@latest init`
- Install `react-markdown` for rendering the draft review

**app/page.tsx — Reviews list**
- Server component, `cache: "no-store"`, fetches `GET /reviews/pending`
- Renders `ReviewCard` per pending review showing PR number and findings counts
- Each card links to `/reviews/[threadId]`

**app/reviews/[threadId]/page.tsx — Review detail**
- Two-column layout: left = draft review rendered as markdown, right = approval form
- Approval form: optional comment textarea, green Approve button, red Reject button
- On approve: `POST /reviews/{threadId}/approve` with comment
- On reject: `POST /reviews/{threadId}/reject`
- On success: redirect to `/` with success toast

Checkpoint: Full end-to-end — open PR on GitHub → review appears in dashboard → click Approve → review posted to GitHub PR.

---

## Critical Details to Never Forget

1. **`findings` merge strategy** — must use `Annotated[List[Finding], operator.add]` in state. Without this, parallel agents silently overwrite each other's results. No error — just missing findings.

2. **`thread_id`** — generate a fresh UUID per PR. This is how LangGraph identifies which checkpoint to resume. Never reuse.

3. **Docker platform** — always `platform="linux/arm64"` on M1. x86 images via Rosetta 2 work but are 2–3x slower.

4. **GitHub webhook response time** — FastAPI must return 200 within 10 seconds or GitHub marks the delivery as failed. Always use `BackgroundTasks` for the graph invocation.

5. **Trim diffs** — cap each file diff at ~3000 characters before sending to Gemini. Large diffs hit context limits and slow responses.

6. **Tenacity retry on both parallel agents** — they call Gemini simultaneously, which occasionally triggers transient rate limits. 3 retries with exponential backoff fixes this silently.

7. **Test nodes standalone first** — never wire a node into the graph until it works correctly when called directly as a Python function.

---

## How to Start This Session

Start with Phase 1, Step 1.1. Build `graph/state.py` first. Explain the `Annotated` merge strategy for `findings` when you write it — I need to understand why it is necessary, not just that it is. After state.py is done, move to `agents/diff_reader.py`.
