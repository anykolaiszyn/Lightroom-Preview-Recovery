# Multi-Agent Idea-to-App Starter Kit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and package an immediately usable, tool-neutral multi-agent software-delivery playbook with Codex, Claude Code, Ollama, and generic-agent adapters.

**Architecture:** The starter kit uses Markdown control files as durable project state, a sequence of lifecycle prompts, tool-specific adapters, and standard-library validation tests. Source files live under `playbooks/multi-agent-idea-to-app/`; a deterministic packaging script produces a handbook and ZIP under `outputs/`.

**Tech Stack:** Markdown, JSON, Python 3.12 standard library (`unittest`, `json`, `zipfile`, `pathlib`, `hashlib`), PowerShell 7.

## Global Constraints

- Cover web, desktop, mobile, CLI, API, automation, data-pipeline, AI-tool, plugin, and internal-utility projects.
- Keep research-only and non-technical business deliverables outside the primary workflow.
- Support Codex, Claude Code, Ollama, and a generic agent without making one provider's chat history authoritative.
- Treat files as project memory; chat history is supporting context only.
- Require human approval after the written design, implementation plan, material scope changes, destructive or externally consequential actions, security/privacy/licensing assumption changes, and release readiness.
- Require a different agent to review each implementation task.
- Do not mark a task complete while Critical or Important findings remain open.
- Use Ollama for low-risk supporting work; do not let Ollama independently approve high-risk or release work.
- Allow parallel work only for dependency-independent tasks with non-overlapping file ownership.
- Package only source-controlled starter-kit files; never include this Lightroom project's source data, outputs, or conversation history.
- Use plain language and provider-neutral terminology in shared templates.
- All validation and packaging must work with the Python standard library and must not require network access.

---

### Task 1: Package Contract and Standalone Validator

**Files:**
- Create: `playbooks/multi-agent-idea-to-app/manifest.json`
- Create: `playbooks/tests/test_multi_agent_starter_kit.py`
- Create: `playbooks/scripts/validate_starter_kit.py`

**Interfaces:**
- Consumes: The approved design at `docs/superpowers/specs/2026-07-25-multi-agent-idea-to-app-playbook-design.md`.
- Produces: `validate(root: Path) -> list[str]`, where an empty list means the kit satisfies the package contract.

- [ ] **Step 1: Write the failing manifest-validation tests**

Create `playbooks/tests/test_multi_agent_starter_kit.py` with:

```python
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "playbooks" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from validate_starter_kit import validate  # noqa: E402


KIT = ROOT / "playbooks" / "multi-agent-idea-to-app"


class StarterKitContractTests(unittest.TestCase):
    def test_manifest_lists_every_required_deliverable(self) -> None:
        manifest = json.loads((KIT / "manifest.json").read_text(encoding="utf-8"))
        required = set(manifest["required_files"])
        self.assertIn("HANDBOOK.md", required)
        self.assertIn("QUICKSTART.md", required)
        self.assertIn("templates/AGENTS.md", required)
        self.assertIn("prompts/05-task-review.md", required)
        self.assertIn("adapters/OLLAMA.md", required)
        self.assertIn("examples/idea-to-app-example.md", required)

    def test_current_kit_satisfies_contract(self) -> None:
        self.assertEqual([], validate(KIT))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify the red state**

Run:

```powershell
C:\Users\alexn\Documents\Codex\.venvs\lrpr\Scripts\python.exe -m unittest discover -s playbooks\tests -p test_multi_agent_starter_kit.py -v
```

Expected: FAIL because the manifest and validator do not exist.

- [ ] **Step 3: Create the exact package manifest**

Create `manifest.json` with:

```json
{
  "name": "Multi-Agent Idea-to-App Starter Kit",
  "version": "1.0.0",
  "required_files": [
    "HANDBOOK.md",
    "QUICKSTART.md",
    "prompts/01-discovery.md",
    "prompts/02-design.md",
    "prompts/03-implementation-plan.md",
    "prompts/04-task-implementation.md",
    "prompts/05-task-review.md",
    "prompts/06-integration.md",
    "prompts/07-release.md",
    "prompts/08-handoff-and-resume.md",
    "templates/AGENTS.md",
    "templates/PROJECT-BRIEF.md",
    "templates/DESIGN-SPEC.md",
    "templates/IMPLEMENTATION-PLAN.md",
    "templates/TASK-BRIEF.md",
    "templates/IMPLEMENTATION-REPORT.md",
    "templates/REVIEW-REPORT.md",
    "templates/PROGRESS-LEDGER.md",
    "templates/RELEASE-CHECKLIST.md",
    "adapters/CODEX.md",
    "adapters/CLAUDE-CODE.md",
    "adapters/OLLAMA.md",
    "adapters/GENERIC-AGENT.md",
    "examples/idea-to-app-example.md"
  ],
  "forbidden_markers": [
    "\u0054BD",
    "\u0054ODO",
    "\u0046ILL THIS IN",
    "\u0069mplement later",
    "\u0073imilar to the previous"
  ]
}
```

- [ ] **Step 4: Implement the minimal validator**

Create `validate_starter_kit.py`:

```python
from __future__ import annotations

import json
from pathlib import Path


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return ["Missing manifest.json"]

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for relative in manifest["required_files"]:
        path = root / relative
        if not path.is_file():
            errors.append(f"Missing required file: {relative}")
            continue
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            errors.append(f"Required file is empty: {relative}")
        for marker in manifest["forbidden_markers"]:
            if marker.casefold() in text.casefold():
                errors.append(f"Forbidden placeholder {marker!r} in {relative}")
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1] / "multi-agent-idea-to-app"
    errors = validate(root)
    if errors:
        for error in errors:
            print(error)
        return 1
    print("Starter kit contract passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the contract test**

Run the Step 2 command.

Expected: one manifest test passes and the current-kit test fails with explicit missing-file messages.

- [ ] **Step 6: Commit**

```powershell
git add playbooks/multi-agent-idea-to-app/manifest.json playbooks/tests/test_multi_agent_starter_kit.py playbooks/scripts/validate_starter_kit.py
git commit -m "test: define multi-agent starter kit contract"
```

---

### Task 2: Durable Project-State Templates

**Files:**
- Create: `playbooks/multi-agent-idea-to-app/templates/AGENTS.md`
- Create: `playbooks/multi-agent-idea-to-app/templates/PROJECT-BRIEF.md`
- Create: `playbooks/multi-agent-idea-to-app/templates/DESIGN-SPEC.md`
- Create: `playbooks/multi-agent-idea-to-app/templates/IMPLEMENTATION-PLAN.md`
- Create: `playbooks/multi-agent-idea-to-app/templates/TASK-BRIEF.md`
- Create: `playbooks/multi-agent-idea-to-app/templates/IMPLEMENTATION-REPORT.md`
- Create: `playbooks/multi-agent-idea-to-app/templates/REVIEW-REPORT.md`
- Create: `playbooks/multi-agent-idea-to-app/templates/PROGRESS-LEDGER.md`
- Create: `playbooks/multi-agent-idea-to-app/templates/RELEASE-CHECKLIST.md`
- Modify: `playbooks/tests/test_multi_agent_starter_kit.py`

**Interfaces:**
- Consumes: The package contract from Task 1.
- Produces: Shared Markdown state files that every tool adapter and lifecycle prompt references by exact filename.

- [ ] **Step 1: Add failing template-content tests**

Add these methods to `StarterKitContractTests`:

```python
    def test_agents_template_defines_authority_and_safety(self) -> None:
        text = (KIT / "templates" / "AGENTS.md").read_text(encoding="utf-8")
        for heading in (
            "## Mission",
            "## Source of truth",
            "## Safety boundaries",
            "## Verification",
            "## Handoff contract",
        ):
            self.assertIn(heading, text)

    def test_task_and_review_templates_enforce_independence(self) -> None:
        task = (KIT / "templates" / "TASK-BRIEF.md").read_text(encoding="utf-8")
        review = (KIT / "templates" / "REVIEW-REPORT.md").read_text(encoding="utf-8")
        self.assertIn("Files owned", task)
        self.assertIn("Red-state evidence", task)
        self.assertIn("Critical findings", review)
        self.assertIn("Important findings", review)
        self.assertIn("The reviewer must not edit", review)

    def test_progress_ledger_has_one_active_task_contract(self) -> None:
        text = (KIT / "templates" / "PROGRESS-LEDGER.md").read_text(encoding="utf-8")
        self.assertIn("Exactly one task may be active", text)
        self.assertIn("Open findings", text)
        self.assertIn("Latest verification", text)
```

- [ ] **Step 2: Run the focused test and verify failure**

Run the Task 1 test command.

Expected: FAIL because the templates are missing.

- [ ] **Step 3: Write the AGENTS and project/design templates**

Write complete, fillable templates with instructional comments that use
bracketed field names such as `[PROJECT NAME]`, never unresolved-marker
vocabulary from the package manifest.

`AGENTS.md` must define:

- Mission and deliverable
- Authoritative control files
- Safety and external-action boundaries
- Commands and verification expectations
- File-ownership rules
- Parallel-work rules
- Review independence
- Handoff-report fields

`PROJECT-BRIEF.md` must define:

- Problem and intended users
- Desired outcome
- Inputs and existing systems
- Constraints and exclusions
- Risks and approvals
- Success measures

`DESIGN-SPEC.md` must define:

- Scope and non-goals
- Options considered and decision
- Architecture and component contracts
- Data flow
- Error and recovery behavior
- Security/privacy/safety
- Testing and release strategy
- Acceptance criteria
- Human approval record

- [ ] **Step 4: Write the plan, task, report, ledger, and release templates**

`IMPLEMENTATION-PLAN.md` must define dependency-ordered tasks, owned files,
interfaces, red/green verification, review gate, and commit/patch checkpoint.

`TASK-BRIEF.md` must define task objective, dependencies, files owned, consumed
and produced interfaces, prohibited changes, red-state evidence, focused/full
test commands, and report location.

`IMPLEMENTATION-REPORT.md` must define changed files, behavior, exact test
results, assumptions, risks, patch/commit identity, and recommended next step.

`REVIEW-REPORT.md` must state that the reviewer does not edit, then define
Critical, Important, and Minor findings, verification performed, prior-finding
disposition, and approval status.

`PROGRESS-LEDGER.md` must require exactly one active task and track lifecycle
phase, dependencies, agent/tool, ownership, review state, open findings,
verification, blockers, decisions, and cost notes.

`RELEASE-CHECKLIST.md` must cover fresh tests, security, dependencies, licenses,
package contents, real-input validation, immutability, smoke testing, report
reconciliation, artifact hashes, limitations, and final independent approval.

- [ ] **Step 5: Run the focused tests**

Run the Task 1 command.

Expected: Template-specific tests pass; the overall contract still reports
missing prompts, adapters, handbook, quickstart, and example.

- [ ] **Step 6: Commit**

```powershell
git add playbooks/multi-agent-idea-to-app/templates playbooks/tests/test_multi_agent_starter_kit.py
git commit -m "docs: add durable multi-agent project templates"
```

---

### Task 3: Lifecycle Prompt Pack

**Files:**
- Create: `playbooks/multi-agent-idea-to-app/prompts/01-discovery.md`
- Create: `playbooks/multi-agent-idea-to-app/prompts/02-design.md`
- Create: `playbooks/multi-agent-idea-to-app/prompts/03-implementation-plan.md`
- Create: `playbooks/multi-agent-idea-to-app/prompts/04-task-implementation.md`
- Create: `playbooks/multi-agent-idea-to-app/prompts/05-task-review.md`
- Create: `playbooks/multi-agent-idea-to-app/prompts/06-integration.md`
- Create: `playbooks/multi-agent-idea-to-app/prompts/07-release.md`
- Create: `playbooks/multi-agent-idea-to-app/prompts/08-handoff-and-resume.md`
- Modify: `playbooks/tests/test_multi_agent_starter_kit.py`

**Interfaces:**
- Consumes: Exact template filenames from Task 2.
- Produces: Copy-ready prompts that move a project through each lifecycle phase without provider-specific syntax.

- [ ] **Step 1: Add failing prompt-contract tests**

Add:

```python
    def test_every_prompt_names_inputs_outputs_and_stop_condition(self) -> None:
        prompt_dir = KIT / "prompts"
        for path in sorted(prompt_dir.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path.name):
                self.assertIn("## Read first", text)
                self.assertIn("## Produce", text)
                self.assertIn("## Stop when", text)

    def test_review_prompt_forbids_edits_and_self_approval(self) -> None:
        text = (KIT / "prompts" / "05-task-review.md").read_text(encoding="utf-8")
        self.assertIn("Do not edit", text)
        self.assertIn("different agent", text)
        self.assertIn("Critical", text)
        self.assertIn("Important", text)

    def test_release_prompt_requires_fresh_artifact_evidence(self) -> None:
        text = (KIT / "prompts" / "07-release.md").read_text(encoding="utf-8")
        self.assertIn("fresh", text.casefold())
        self.assertIn("packaged artifact", text.casefold())
        self.assertIn("smoke test", text.casefold())
        self.assertIn("license", text.casefold())
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run the Task 1 command.

Expected: FAIL because prompt files are absent.

- [ ] **Step 3: Write discovery, design, and planning prompts**

Each prompt must include:

- Purpose
- Role
- `## Read first`
- Exact actions
- `## Produce`
- Verification
- `## Stop when`

`01-discovery.md` instructs the agent to inspect inputs read-only, identify the
user and outcome, inventory existing systems, identify risk and unknowns, and
write `PROJECT-BRIEF.md`.

`02-design.md` instructs the agent to ask one question at a time, offer two or
three approaches, recommend one, obtain section-by-section approval, write
`DESIGN-SPEC.md`, self-review it, and stop for written approval.

`03-implementation-plan.md` instructs the agent to map files and interfaces,
split work into independently reviewable tasks, include red/green steps and
exact commands, identify safe parallelism, write `IMPLEMENTATION-PLAN.md`, and
stop for approval.

- [ ] **Step 4: Write implementation, review, and integration prompts**

`04-task-implementation.md` requires an approved task brief, explicit
ownership, red-state evidence, scoped edits, focused/full tests, and
`IMPLEMENTATION-REPORT.md`.

`05-task-review.md` requires a different agent, prohibits edits, requires the
actual diff and surrounding context, and produces a structured
`REVIEW-REPORT.md`.

`06-integration.md` requires all component tasks to be approved, validates
interfaces and combined behavior, runs integration tests, and returns new
cross-task findings to bounded task loops.

- [ ] **Step 5: Write release and resume prompts**

`07-release.md` requires fresh source tests, security/dependency/license review,
package-content scan, packaged-artifact launch, bounded real-input smoke test,
output reconciliation, hashes, limitations, and independent release approval.

`08-handoff-and-resume.md` instructs a new agent to read control files, inspect
the working tree, resume only the ledger's active task, preserve uncommitted
work, and write a structured final handoff.

- [ ] **Step 6: Run the prompt tests**

Run the Task 1 command.

Expected: Prompt tests pass; overall contract still reports adapters,
handbook, quickstart, and example as missing.

- [ ] **Step 7: Commit**

```powershell
git add playbooks/multi-agent-idea-to-app/prompts playbooks/tests/test_multi_agent_starter_kit.py
git commit -m "docs: add multi-agent lifecycle prompt pack"
```

---

### Task 4: Codex, Claude Code, Ollama, and Generic Adapters

**Files:**
- Create: `playbooks/multi-agent-idea-to-app/adapters/CODEX.md`
- Create: `playbooks/multi-agent-idea-to-app/adapters/CLAUDE-CODE.md`
- Create: `playbooks/multi-agent-idea-to-app/adapters/OLLAMA.md`
- Create: `playbooks/multi-agent-idea-to-app/adapters/GENERIC-AGENT.md`
- Modify: `playbooks/tests/test_multi_agent_starter_kit.py`

**Interfaces:**
- Consumes: Shared templates and prompts.
- Produces: Tool-specific setup, invocation, context, isolation, and handoff guidance that does not change the shared lifecycle.

- [ ] **Step 1: Add failing adapter tests**

Add:

```python
    def test_adapters_preserve_shared_control_files(self) -> None:
        for name in ("CODEX.md", "CLAUDE-CODE.md", "OLLAMA.md", "GENERIC-AGENT.md"):
            text = (KIT / "adapters" / name).read_text(encoding="utf-8")
            with self.subTest(adapter=name):
                self.assertIn("PROGRESS-LEDGER.md", text)
                self.assertIn("TASK-BRIEF.md", text)
                self.assertIn("REVIEW-REPORT.md", text)
                self.assertIn("Do not change the lifecycle", text)

    def test_ollama_adapter_limits_release_authority(self) -> None:
        text = (KIT / "adapters" / "OLLAMA.md").read_text(encoding="utf-8")
        self.assertIn("low-risk", text.casefold())
        self.assertIn("must not independently approve", text.casefold())
        self.assertIn("final release", text.casefold())
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run the Task 1 command.

Expected: FAIL because adapters are absent.

- [ ] **Step 3: Write the Codex adapter**

Cover:

- Opening the repository/folder in Codex
- Root and nested `AGENTS.md`
- Prompt/thread context for one-off task constraints
- Subagents for bounded implementation and review
- Worktrees for concurrent repository changes
- Fresh reviewer per task
- Durable reports and ledger
- Permission and approval boundaries
- Exact kickoff and resume examples

Link only to official Codex documentation for Codex-specific claims.

- [ ] **Step 4: Write the Claude Code adapter**

Cover:

- Repository guidance file and task context
- Bounded subagent prompts
- File ownership and isolated branches/worktrees
- Separate implementer/reviewer sessions
- Exact kickoff and resume examples
- The shared files remain authoritative

Avoid claims about unstable features unless supported by current official
Anthropic documentation.

- [ ] **Step 5: Write the Ollama adapter**

Cover:

- Selecting a code-capable local model
- Supplying only the required control and source files
- A command/prompt wrapper that names allowed files and commands
- Low-risk task routing
- Structured output capture into implementation/review reports
- Context-window and model-capability limits
- Escalation to Codex or Claude for high-risk decisions
- No independent release approval

- [ ] **Step 6: Write the generic adapter**

Define the minimum contract for any agent:

- Can read a bounded context bundle
- Can produce a patch or owned files
- Can execute or report tests
- Can write the structured task report
- Cannot silently change scope or authority

- [ ] **Step 7: Run adapter tests**

Run the Task 1 command.

Expected: Adapter tests pass; overall contract still reports handbook,
quickstart, and example as missing.

- [ ] **Step 8: Commit**

```powershell
git add playbooks/multi-agent-idea-to-app/adapters playbooks/tests/test_multi_agent_starter_kit.py
git commit -m "docs: add Codex Claude Ollama agent adapters"
```

---

### Task 5: Handbook, Quickstart, and Worked Example

**Files:**
- Create: `playbooks/multi-agent-idea-to-app/HANDBOOK.md`
- Create: `playbooks/multi-agent-idea-to-app/QUICKSTART.md`
- Create: `playbooks/multi-agent-idea-to-app/examples/idea-to-app-example.md`
- Modify: `playbooks/tests/test_multi_agent_starter_kit.py`

**Interfaces:**
- Consumes: All templates, prompts, and adapters.
- Produces: A learnable long-form guide, a short launch path, and a complete worked example.

- [ ] **Step 1: Add failing reader-facing content tests**

Add:

```python
    def test_handbook_explains_complete_lifecycle(self) -> None:
        text = (KIT / "HANDBOOK.md").read_text(encoding="utf-8")
        for heading in (
            "## Why this works",
            "## Lifecycle",
            "## Agent roles",
            "## Human approval gates",
            "## Quality gates",
            "## Cost controls",
            "## Switching tools",
            "## Failure and recovery",
        ):
            self.assertIn(heading, text)
        for phase in (
            "Discovery",
            "Options and Design",
            "Implementation Planning",
            "Task Loop",
            "Integration",
            "Real-World Validation",
            "Release",
            "Handoff",
        ):
            self.assertIn(phase, text)

    def test_handbook_defines_every_agent_role(self) -> None:
        text = (KIT / "HANDBOOK.md").read_text(encoding="utf-8")
        for role in (
            "Lead Orchestrator",
            "Architect",
            "Implementer",
            "Independent Reviewer",
            "Local Supporting Agent",
            "Release Reviewer",
        ):
            self.assertIn(role, text)

    def test_quickstart_is_actionable(self) -> None:
        text = (KIT / "QUICKSTART.md").read_text(encoding="utf-8")
        self.assertIn("Copy the templates", text)
        self.assertIn("Start with discovery", text)
        self.assertIn("Approve the written design", text)
        self.assertIn("Do not release", text)

    def test_example_reaches_reviewed_release(self) -> None:
        text = (KIT / "examples" / "idea-to-app-example.md").read_text(encoding="utf-8")
        for phrase in (
            "Initial idea",
            "Options considered",
            "Approved design",
            "Task brief",
            "Independent review",
            "Release evidence",
            "Handoff",
        ):
            self.assertIn(phrase, text)
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run the Task 1 command.

Expected: FAIL because the reader-facing files are absent.

- [ ] **Step 3: Write the handbook**

The handbook must:

- Explain why durable artifacts outperform chat-only state
- Walk through the eight named phases: Discovery, Options and Design,
  Implementation Planning, Task Loop, Integration, Real-World Validation,
  Release, and Handoff
- Define Lead Orchestrator, Architect, Implementer, Independent Reviewer, Local
  Supporting Agent, and Release Reviewer responsibilities and provider routing
- Explain design and plan approval gates
- Explain TDD and independent review loops
- Explain safe parallelism and worktree/branch isolation
- Explain real-input validation and release evidence
- Explain switching among Codex, Claude, and Ollama
- Explain interruption, quota exhaustion, partial work, and resume
- Include quality and cost-control checklists
- Link to the prompt and template files instead of duplicating them wholesale

- [ ] **Step 4: Write the quickstart**

Limit the quickstart to:

1. Copy templates into a new project
2. Fill `PROJECT-BRIEF.md`
3. Launch the discovery prompt
4. Approve written design
5. Approve implementation plan
6. Run task implementation/review loops
7. Integrate and validate
8. Release only after the checklist passes

Include one Codex-first kickoff example and one cross-tool handoff example.

- [ ] **Step 5: Write the worked example**

Use a fictional "Local Receipt Organizer" desktop utility. Show:

- The initial user idea
- Discovery evidence and constraints
- Three approaches and the chosen design
- A three-task implementation plan
- One task assigned to Ollama for fixtures
- One task assigned to Codex or Claude for filesystem safety
- A separate reviewer finding an unsafe overwrite
- A regression fix and re-review
- Integration, bounded real-input test, package review, release evidence, and
  handoff

Do not claim that executable code was produced; the example demonstrates the
workflow and artifacts.

- [ ] **Step 6: Run the complete starter-kit validator suite**

Run:

```powershell
C:\Users\alexn\Documents\Codex\.venvs\lrpr\Scripts\python.exe -m unittest discover -s playbooks\tests -p test_multi_agent_starter_kit.py -v
C:\Users\alexn\Documents\Codex\.venvs\lrpr\Scripts\python.exe playbooks\scripts\validate_starter_kit.py
```

Expected: all tests pass and validator prints `Starter kit contract passed.`

- [ ] **Step 7: Commit**

```powershell
git add playbooks/multi-agent-idea-to-app/HANDBOOK.md playbooks/multi-agent-idea-to-app/QUICKSTART.md playbooks/multi-agent-idea-to-app/examples playbooks/tests/test_multi_agent_starter_kit.py
git commit -m "docs: complete multi-agent idea-to-app handbook"
```

---

### Task 6: Deterministic Packaging and Reader Handoff

**Files:**
- Create: `playbooks/scripts/package_starter_kit.py`
- Modify: `playbooks/tests/test_multi_agent_starter_kit.py`
- Create: `outputs/Multi-Agent-Idea-to-App-Handbook.md`
- Create: `outputs/Multi-Agent-Idea-to-App-Starter-Kit.zip`

**Interfaces:**
- Consumes: Validated source kit.
- Produces: A stable ZIP and standalone handbook for the user.

- [ ] **Step 1: Add failing package tests**

Add:

```python
    def test_package_script_is_deterministic_and_safe(self) -> None:
        script = (ROOT / "playbooks" / "scripts" / "package_starter_kit.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("ZipInfo", script)
        self.assertIn("(1980, 1, 1, 0, 0, 0)", script)
        self.assertIn("manifest.json", script)
        self.assertIn("outputs", script)
```

- [ ] **Step 2: Run the focused test and verify failure**

Run the Task 5 unittest command.

Expected: FAIL because `package_starter_kit.py` is absent.

- [ ] **Step 3: Implement deterministic packaging**

Create a standard-library script that:

- Calls `validate(KIT)` and exits nonzero on any error
- Deletes only the exact prior ZIP/handbook outputs
- Copies `HANDBOOK.md` byte-for-byte to the output handbook
- Adds `manifest.json` and every `required_files` entry to the ZIP
- Uses forward-slash archive names under `Multi-Agent-Idea-to-App/`
- Uses `ZipInfo.date_time = (1980, 1, 1, 0, 0, 0)`
- Uses UTF-8 text bytes and `ZIP_DEFLATED`
- Rejects absolute paths, `..` components, symlinks, and files outside the kit
- Prints ZIP and handbook SHA-256 hashes

- [ ] **Step 4: Run tests and package**

Run:

```powershell
C:\Users\alexn\Documents\Codex\.venvs\lrpr\Scripts\python.exe -m unittest discover -s playbooks\tests -p test_multi_agent_starter_kit.py -v
C:\Users\alexn\Documents\Codex\.venvs\lrpr\Scripts\python.exe playbooks\scripts\package_starter_kit.py
```

Expected: Tests pass and both output files are created with printed hashes.

- [ ] **Step 5: Verify archive contents and deterministic rebuild**

Run the packaging script twice and compare hashes. Inspect with:

```powershell
Get-FileHash outputs\Multi-Agent-Idea-to-App-Starter-Kit.zip -Algorithm SHA256
Get-FileHash outputs\Multi-Agent-Idea-to-App-Handbook.md -Algorithm SHA256
```

Expected: the second run produces identical hashes and the archive contains
only the manifest and required starter-kit files.

- [ ] **Step 6: Run a final independent review**

Give a fresh reviewer:

- The approved design
- This plan
- All source kit files
- Validator/test output
- ZIP listing and hashes

Require Critical/Important/Minor findings, fix/re-review loops, and explicit
approval before delivery.

- [ ] **Step 7: Commit**

```powershell
git add playbooks/scripts/package_starter_kit.py playbooks/tests/test_multi_agent_starter_kit.py
git commit -m "build: package multi-agent starter kit"
```
