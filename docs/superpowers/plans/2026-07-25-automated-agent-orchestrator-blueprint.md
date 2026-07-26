# Automated Multi-Agent Orchestrator Blueprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a complete, non-runnable architecture blueprint for a future local orchestrator that routes bounded software-delivery tasks among Codex, Claude Code, Ollama, and generic agents.

**Architecture:** The blueprint separates lifecycle control, scheduling, provider routing, permissions, evidence, review gates, cost tracking, and human approvals. Provider-neutral JSON Schemas define project, task, and review state; Markdown documents define behavior, interfaces, safety, and a staged implementation roadmap.

**Tech Stack:** Markdown, JSON Schema Draft 2020-12, Python 3.12 standard library (`unittest`, `json`, `zipfile`, `pathlib`, `hashlib`), PowerShell 7.

## Global Constraints

- The deliverable is an architecture blueprint, not runnable orchestration code.
- Keep the blueprint separate from the Hybrid Multi-Agent Starter Kit.
- Support Codex, Claude Code, Ollama, and a generic command-based agent adapter.
- Use file-backed durable state and an append-only audit/event trail.
- Do not let chat history become authoritative state.
- Enforce task-scoped context and least-privilege filesystem, command, network, credential, and external-action access.
- Require human approval at design, implementation-plan, material-scope, destructive/external-action, security/privacy/licensing, and release gates.
- Require a reviewer identity distinct from the implementer.
- Block integration while Critical or Important findings remain open.
- Pause on provider failure, missing evidence, or budget exhaustion; never silently skip a quality gate.
- Define schemas and interfaces precisely enough for later implementation without committing to one provider SDK.
- Do not include secrets, credentials, account identifiers, or private project data.
- Use only standard-library offline validation and packaging.

---

### Task 1: Blueprint Contract and Validation Harness

**Files:**
- Create: `playbooks/automated-orchestrator-blueprint/manifest.json`
- Create: `playbooks/tests/test_orchestrator_blueprint.py`
- Create: `playbooks/scripts/validate_orchestrator_blueprint.py`

**Interfaces:**
- Consumes: The approved playbook design specification.
- Produces: `validate(root: Path) -> list[str]` for required-file, placeholder, JSON, and schema-identity checks.

- [ ] **Step 1: Write failing contract tests**

Create `playbooks/tests/test_orchestrator_blueprint.py`:

```python
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "playbooks" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from validate_orchestrator_blueprint import validate  # noqa: E402


BLUEPRINT = ROOT / "playbooks" / "automated-orchestrator-blueprint"


class OrchestratorBlueprintContractTests(unittest.TestCase):
    def test_manifest_defines_separate_non_runnable_blueprint(self) -> None:
        manifest = json.loads((BLUEPRINT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual("architecture-blueprint", manifest["artifact_type"])
        self.assertFalse(manifest["contains_runnable_orchestrator"])
        self.assertIn("ARCHITECTURE.md", manifest["required_files"])
        self.assertIn("schemas/task.schema.json", manifest["required_files"])

    def test_blueprint_satisfies_contract(self) -> None:
        self.assertEqual([], validate(BLUEPRINT))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify the red state**

Run:

```powershell
C:\Users\alexn\Documents\Codex\.venvs\lrpr\Scripts\python.exe -m unittest discover -s playbooks\tests -p test_orchestrator_blueprint.py -v
```

Expected: FAIL because the blueprint manifest and validator are absent.

- [ ] **Step 3: Create the manifest**

Create:

```json
{
  "name": "Automated Multi-Agent Orchestrator Blueprint",
  "version": "1.0.0",
  "artifact_type": "architecture-blueprint",
  "contains_runnable_orchestrator": false,
  "required_files": [
    "ARCHITECTURE.md",
    "AGENT-ROUTING.md",
    "SECURITY-AND-PERMISSIONS.md",
    "STATE-MODEL.md",
    "PROVIDER-ADAPTERS.md",
    "HUMAN-APPROVAL-GATES.md",
    "OBSERVABILITY-AND-COSTS.md",
    "IMPLEMENTATION-ROADMAP.md",
    "schemas/project-state.schema.json",
    "schemas/task.schema.json",
    "schemas/review.schema.json"
  ],
  "schema_dialect": "https://json-schema.org/draft/2020-12/schema",
  "forbidden_markers": [
    "\u0054BD",
    "\u0054ODO",
    "\u0046ILL THIS IN",
    "\u0069mplement later"
  ]
}
```

- [ ] **Step 4: Implement the validator**

The validator must:

- Require and parse `manifest.json`
- Require every file listed in `required_files`
- Reject empty files and forbidden markers
- Parse every `.json` file
- Require each schema's `$schema` to equal the manifest dialect
- Require each schema to have `$id`, `title`, `type`, `required`, and
  `additionalProperties`
- Return all validation errors instead of failing on the first one
- Provide a CLI that prints errors and exits 1, or prints
  `Orchestrator blueprint contract passed.` and exits 0

- [ ] **Step 5: Run the focused test**

Run the Step 2 command.

Expected: Manifest test passes; contract test reports the missing blueprint
documents and schemas.

- [ ] **Step 6: Commit**

```powershell
git add playbooks/automated-orchestrator-blueprint/manifest.json playbooks/tests/test_orchestrator_blueprint.py playbooks/scripts/validate_orchestrator_blueprint.py
git commit -m "test: define orchestrator blueprint contract"
```

---

### Task 2: Project, Task, and Review Schemas

**Files:**
- Create: `playbooks/automated-orchestrator-blueprint/schemas/project-state.schema.json`
- Create: `playbooks/automated-orchestrator-blueprint/schemas/task.schema.json`
- Create: `playbooks/automated-orchestrator-blueprint/schemas/review.schema.json`
- Modify: `playbooks/tests/test_orchestrator_blueprint.py`

**Interfaces:**
- Consumes: JSON Schema dialect from the manifest.
- Produces:
  - `project-state.schema.json`: lifecycle, approvals, active task, artifacts, events, and budget state.
  - `task.schema.json`: dependencies, ownership, risk, provider assignment, permissions, evidence, and status.
  - `review.schema.json`: reviewer identity, findings, verification, dispositions, and approval.

- [ ] **Step 1: Add failing schema-structure tests**

Add:

```python
    def _schema(self, name: str) -> dict:
        return json.loads(
            (BLUEPRINT / "schemas" / name).read_text(encoding="utf-8")
        )

    def test_task_schema_encodes_ownership_risk_and_permissions(self) -> None:
        properties = self._schema("task.schema.json")["properties"]
        for key in (
            "task_id",
            "dependencies",
            "owned_paths",
            "risk",
            "assigned_provider",
            "permissions",
            "status",
            "evidence",
        ):
            self.assertIn(key, properties)

    def test_review_schema_blocks_implicit_self_approval(self) -> None:
        schema = self._schema("review.schema.json")
        properties = schema["properties"]
        self.assertIn("implementer_identity", properties)
        self.assertIn("reviewer_identity", properties)
        self.assertIn("findings", properties)
        self.assertIn("approval", properties)

    def test_project_schema_has_approval_and_budget_state(self) -> None:
        properties = self._schema("project-state.schema.json")["properties"]
        self.assertIn("lifecycle_phase", properties)
        self.assertIn("active_task_id", properties)
        self.assertIn("approvals", properties)
        self.assertIn("budget", properties)
        self.assertIn("event_log", properties)
```

- [ ] **Step 2: Run tests and verify failure**

Run the Task 1 unittest command.

Expected: FAIL because schemas are absent.

- [ ] **Step 3: Write `task.schema.json`**

Use Draft 2020-12 and require:

- `task_id`: non-empty string
- `title`: non-empty string
- `objective`: non-empty string
- `dependencies`: unique string array
- `owned_paths`: unique relative-path string array
- `risk`: object with integer scores 0–3 for destructive, security, privacy,
  external-effects, concurrency, reversibility, and release-impact dimensions
- `assigned_provider`: enum `codex`, `claude-code`, `ollama`, `generic`, or
  `unassigned`
- `permissions`: object containing allowed read paths, write paths, commands,
  network destinations, credentials, and external actions
- `status`: enum `pending`, `ready`, `active`, `implemented`, `in_review`,
  `changes_requested`, `approved`, `blocked`, `integrated`, `cancelled`
- `evidence`: array of typed evidence references
- `implementation_report`: nullable relative path
- `review_report`: nullable relative path
- `additionalProperties: false`

- [ ] **Step 4: Write `review.schema.json`**

Require:

- `review_id`, `task_id`, `implementer_identity`, and `reviewer_identity`
- `findings`: array of objects with identifier, severity enum, title,
  evidence, status, disposition, and regression evidence
- `verification`: command/result references
- `prior_findings_checked`: identifier array
- `approval`: enum `approved`, `changes_requested`, `blocked`
- `created_at`: ISO date-time string
- `additionalProperties: false`

Document in `description` that runtime logic must reject identical implementer
and reviewer identities; JSON Schema records the identities but does not
perform cross-field inequality.

- [ ] **Step 5: Write `project-state.schema.json`**

Require:

- `project_id`, `name`, `objective`, `lifecycle_phase`, and `design_version`
- `active_task_id`: string or null
- `task_ids`: unique string array
- `approvals`: array of gate, decision, actor, timestamp, and evidence
- `artifacts`: typed path/hash records
- `budget`: currency/credit unit, limit, consumed, remaining, and
  exhaustion-policy fields
- `event_log`: append-only event-reference array
- `blocked_reason`: string or null
- `additionalProperties: false`

- [ ] **Step 6: Run schema tests and validator**

Run:

```powershell
C:\Users\alexn\Documents\Codex\.venvs\lrpr\Scripts\python.exe -m unittest discover -s playbooks\tests -p test_orchestrator_blueprint.py -v
C:\Users\alexn\Documents\Codex\.venvs\lrpr\Scripts\python.exe playbooks\scripts\validate_orchestrator_blueprint.py
```

Expected: Schema tests pass; overall validator still reports missing Markdown
blueprint documents.

- [ ] **Step 7: Commit**

```powershell
git add playbooks/automated-orchestrator-blueprint/schemas playbooks/tests/test_orchestrator_blueprint.py
git commit -m "docs: define orchestrator state schemas"
```

---

### Task 3: Architecture and State Model

**Files:**
- Create: `playbooks/automated-orchestrator-blueprint/ARCHITECTURE.md`
- Create: `playbooks/automated-orchestrator-blueprint/STATE-MODEL.md`
- Modify: `playbooks/tests/test_orchestrator_blueprint.py`

**Interfaces:**
- Consumes: Schemas from Task 2.
- Produces: Component responsibilities, lifecycle transitions, event model, concurrency rules, failure recovery, and persistence contract.

- [ ] **Step 1: Add failing architecture tests**

Add:

```python
    def test_architecture_defines_every_controller_component(self) -> None:
        text = (BLUEPRINT / "ARCHITECTURE.md").read_text(encoding="utf-8")
        for heading in (
            "## Project controller",
            "## State store",
            "## Task scheduler",
            "## Agent router",
            "## Permission broker",
            "## Review gate",
            "## Evidence collector",
            "## Cost and usage tracker",
            "## Human approval interface",
        ):
            self.assertIn(heading, text)

    def test_state_model_defines_recovery_and_append_only_events(self) -> None:
        text = (BLUEPRINT / "STATE-MODEL.md").read_text(encoding="utf-8")
        self.assertIn("append-only", text.casefold())
        self.assertIn("interrupted", text.casefold())
        self.assertIn("idempotency", text.casefold())
        self.assertIn("Exactly one active lifecycle transition", text)
```

- [ ] **Step 2: Run tests and verify failure**

Run the Task 1 unittest command.

Expected: FAIL because documents are absent.

- [ ] **Step 3: Write `ARCHITECTURE.md`**

Define:

- System context and non-goals
- The nine named components
- Command/query/event boundaries
- Provider-neutral adapter boundary
- Control-plane versus agent-execution-plane separation
- Worktree/process isolation
- Artifact and evidence storage
- Dependency-ready scheduling
- Review and human-approval gates
- Sequence flows for normal task, changes-requested loop, provider failure,
  budget exhaustion, and release
- Deployment assumption: local single-user controller first

Explicitly state that the blueprint does not supply executable code.

- [ ] **Step 4: Write `STATE-MODEL.md`**

Define:

- Authoritative materialized project state
- Append-only event entries with event ID, prior-event hash, timestamp, actor,
  command ID, payload type, and payload reference
- One active lifecycle transition at a time
- Task-state transition table
- Review-state transition table
- Approval-gate transition table
- Optimistic concurrency/version checks
- Idempotent command keys
- Crash recovery from the latest valid event
- Interrupted tasks remain incomplete
- Evidence records are immutable and content-addressed
- Retention and secret-redaction boundaries

- [ ] **Step 5: Run architecture tests**

Run the Task 1 unittest command.

Expected: Architecture/state tests pass; validator still reports other
documents missing.

- [ ] **Step 6: Commit**

```powershell
git add playbooks/automated-orchestrator-blueprint/ARCHITECTURE.md playbooks/automated-orchestrator-blueprint/STATE-MODEL.md playbooks/tests/test_orchestrator_blueprint.py
git commit -m "docs: design orchestrator architecture and state"
```

---

### Task 4: Provider Interfaces and Agent Routing

**Files:**
- Create: `playbooks/automated-orchestrator-blueprint/PROVIDER-ADAPTERS.md`
- Create: `playbooks/automated-orchestrator-blueprint/AGENT-ROUTING.md`
- Modify: `playbooks/tests/test_orchestrator_blueprint.py`

**Interfaces:**
- Consumes: Task risk, permission, provider, status, and evidence fields.
- Produces: Provider-neutral execution contract and deterministic routing policy.

- [ ] **Step 1: Add failing provider/routing tests**

Add:

```python
    def test_provider_contract_has_required_operations(self) -> None:
        text = (BLUEPRINT / "PROVIDER-ADAPTERS.md").read_text(encoding="utf-8")
        for operation in (
            "prepare_context",
            "start_task",
            "poll_task",
            "cancel_task",
            "collect_evidence",
            "health_check",
        ):
            self.assertIn(operation, text)

    def test_routing_never_assigns_high_risk_release_to_ollama(self) -> None:
        text = (BLUEPRINT / "AGENT-ROUTING.md").read_text(encoding="utf-8")
        self.assertIn("Ollama must not independently approve", text)
        self.assertIn("release-impact", text)
        self.assertIn("provider unavailable", text.casefold())
        self.assertIn("budget exhaustion", text.casefold())
```

- [ ] **Step 2: Run tests and verify failure**

Run the Task 1 unittest command.

Expected: FAIL because provider/routing documents are absent.

- [ ] **Step 3: Write provider adapter contracts**

For every adapter, define typed conceptual requests/responses for:

- `prepare_context(task, permitted_files) -> ContextBundle`
- `start_task(task, context, permission_token) -> RunHandle`
- `poll_task(run_handle) -> RunStatus`
- `cancel_task(run_handle) -> CancellationResult`
- `collect_evidence(run_handle) -> EvidenceBundle`
- `health_check() -> ProviderHealth`

Define common status, error, cancellation, timeout, token/usage, and provenance
fields.

Add provider-specific considerations for:

- Codex: local repository/worktree and subagent execution
- Claude Code: repository context and task-scoped sessions
- Ollama: local endpoint, model identity, context limits, and no hidden cloud
  fallback
- Generic command agent: executable, arguments, environment allowlist, stdin
  context, stdout report, and exit status

Do not specify credentials or unstable vendor API fields.

- [ ] **Step 4: Write deterministic routing policy**

Define:

- Eligibility filters before scoring
- Capability, risk, context, privacy/offline, latency, cost, and availability
  inputs
- Risk override that prevents local supporting models from independently
  approving high-risk or release tasks
- Separate implementer and reviewer identity/provider constraints
- Budget reservation before start
- Provider-unavailable behavior
- Context-too-large behavior
- Budget-exhaustion pause
- Manual override with recorded approval
- Routing-decision evidence record

Include a table with recommended default routes for exploration, documentation,
routine implementation, filesystem safety, concurrency, security, packaging,
and final release review.

- [ ] **Step 5: Run provider/routing tests**

Run the Task 1 unittest command.

Expected: Provider/routing tests pass; remaining documents are missing.

- [ ] **Step 6: Commit**

```powershell
git add playbooks/automated-orchestrator-blueprint/PROVIDER-ADAPTERS.md playbooks/automated-orchestrator-blueprint/AGENT-ROUTING.md playbooks/tests/test_orchestrator_blueprint.py
git commit -m "docs: define agent providers and routing policy"
```

---

### Task 5: Security, Permissions, and Human Approval Gates

**Files:**
- Create: `playbooks/automated-orchestrator-blueprint/SECURITY-AND-PERMISSIONS.md`
- Create: `playbooks/automated-orchestrator-blueprint/HUMAN-APPROVAL-GATES.md`
- Modify: `playbooks/tests/test_orchestrator_blueprint.py`

**Interfaces:**
- Consumes: Task permission and risk fields, project approval records.
- Produces: Threat model, least-privilege permission model, and unskippable approval behavior.

- [ ] **Step 1: Add failing security/approval tests**

Add:

```python
    def test_security_model_covers_secrets_scope_and_audit(self) -> None:
        text = (BLUEPRINT / "SECURITY-AND-PERMISSIONS.md").read_text(encoding="utf-8")
        for phrase in (
            "least privilege",
            "Secrets never enter prompts",
            "path traversal",
            "command allowlist",
            "network destination",
            "audit trail",
            "revocation",
        ):
            self.assertIn(phrase, text)

    def test_human_gates_cannot_be_silently_skipped(self) -> None:
        text = (BLUEPRINT / "HUMAN-APPROVAL-GATES.md").read_text(encoding="utf-8")
        for gate in (
            "Design approval",
            "Implementation-plan approval",
            "Scope-change approval",
            "Destructive-action approval",
            "Release approval",
        ):
            self.assertIn(gate, text)
        self.assertIn("must pause", text.casefold())
```

- [ ] **Step 2: Run tests and verify failure**

Run the Task 1 unittest command.

Expected: FAIL because security and gate documents are absent.

- [ ] **Step 3: Write security and permissions design**

Cover:

- Assets, actors, trust boundaries, and threat scenarios
- Malicious/untrusted repository content and prompt injection
- Path traversal, symlink/reparse escape, and workspace containment
- Command allowlist and argument validation
- Network destination and method allowlist
- Credential handles rather than prompt-visible secrets
- External-action capability tokens
- Permission issuance, expiry, revocation, and audit
- Read/write separation
- Destructive-action confirmation
- Provider context minimization
- Log/evidence redaction
- Worktree and process isolation
- Incident stop and recovery

- [ ] **Step 4: Write human approval gates**

For each gate define:

- Trigger
- Evidence presented
- Allowed decisions: approve, revise, or stop
- Identity and timestamp record
- State transition
- Expiration or invalidation conditions

Include gates for design, plan, scope change, destructive/external action,
security/privacy/licensing assumption change, and release.

Explicitly state that provider failure, missing UI, timeout, or budget
exhaustion must pause; none may default to approval.

- [ ] **Step 5: Run tests**

Run the Task 1 unittest command.

Expected: Security/approval tests pass; observability and roadmap documents
remain missing.

- [ ] **Step 6: Commit**

```powershell
git add playbooks/automated-orchestrator-blueprint/SECURITY-AND-PERMISSIONS.md playbooks/automated-orchestrator-blueprint/HUMAN-APPROVAL-GATES.md playbooks/tests/test_orchestrator_blueprint.py
git commit -m "docs: define orchestrator permissions and approvals"
```

---

### Task 6: Evidence, Observability, Costs, and Failure Recovery

**Files:**
- Create: `playbooks/automated-orchestrator-blueprint/OBSERVABILITY-AND-COSTS.md`
- Modify: `playbooks/tests/test_orchestrator_blueprint.py`

**Interfaces:**
- Consumes: Provider run, project event, task evidence, and budget records.
- Produces: Evidence taxonomy, trace model, cost ledger, dashboards, alerts, retention, and recovery rules.

- [ ] **Step 1: Add failing observability tests**

Add:

```python
    def test_observability_covers_evidence_costs_and_recovery(self) -> None:
        text = (BLUEPRINT / "OBSERVABILITY-AND-COSTS.md").read_text(encoding="utf-8")
        for phrase in (
            "Evidence types",
            "Cost reservation",
            "Budget exhaustion",
            "Provider health",
            "Interrupted run",
            "Redaction",
            "Release evidence",
        ):
            self.assertIn(phrase, text)
```

- [ ] **Step 2: Run tests and verify failure**

Run the Task 1 unittest command.

Expected: FAIL because the document is absent.

- [ ] **Step 3: Write evidence and observability model**

Define evidence types for:

- Selected context and its hashes
- Prompts/instructions
- Patches and changed-file lists
- Commands and exit statuses
- Focused/full/integration test results
- Review reports and finding dispositions
- Approval decisions
- Package listings and hashes
- Smoke and real-input validation

Define:

- Correlation IDs across project/task/run/review
- Provider health and latency
- Queue and task-state metrics
- Failure and retry counters
- Structured logs with secret redaction
- Audit export
- Retention classes

- [ ] **Step 4: Write cost and recovery model**

Define:

- Estimated and reserved cost before start
- Actual provider/model usage
- Local-compute cost notation
- Project/task/provider budgets
- Budget warning thresholds
- Budget exhaustion pauses
- No automatic quality-gate downgrade
- Provider failure, timeout, cancellation, controller crash, evidence-write
  failure, and interrupted-run recovery
- Idempotent restart and orphaned-run reconciliation

- [ ] **Step 5: Run observability tests**

Run the Task 1 unittest command.

Expected: Observability tests pass; roadmap remains missing.

- [ ] **Step 6: Commit**

```powershell
git add playbooks/automated-orchestrator-blueprint/OBSERVABILITY-AND-COSTS.md playbooks/tests/test_orchestrator_blueprint.py
git commit -m "docs: design orchestrator evidence and costs"
```

---

### Task 7: Staged Implementation Roadmap

**Files:**
- Create: `playbooks/automated-orchestrator-blueprint/IMPLEMENTATION-ROADMAP.md`
- Modify: `playbooks/tests/test_orchestrator_blueprint.py`

**Interfaces:**
- Consumes: The complete architecture blueprint.
- Produces: Ten independently reviewable future implementation stages with acceptance, tests, and security gates.

- [ ] **Step 1: Add failing roadmap tests**

Add:

```python
    def test_roadmap_has_ten_gated_stages(self) -> None:
        text = (BLUEPRINT / "IMPLEMENTATION-ROADMAP.md").read_text(encoding="utf-8")
        for number in range(1, 11):
            self.assertIn(f"## Stage {number}:", text)
        self.assertIn("Exit criteria", text)
        self.assertIn("Threat review", text)
        self.assertIn("Rollback", text)
```

- [ ] **Step 2: Run tests and verify failure**

Run the Task 1 unittest command.

Expected: FAIL because the roadmap is absent.

- [ ] **Step 3: Write stages 1–5**

Define:

1. File-backed single-project controller
2. Ollama adapter
3. One cloud-provider adapter
4. Task scheduler and ownership enforcement
5. Evidence collector and independent review gate

For every stage include:

- Scope and exclusions
- Produced interfaces
- Test strategy
- Threat review
- Migration/rollback
- Exit criteria

- [ ] **Step 4: Write stages 6–10**

Define:

6. Human approval interface
7. Cost and usage tracking
8. Additional provider adapters
9. Isolated worktree execution
10. Recovery, audit export, and release hardening

Use the same required subsections as stages 1–5.

- [ ] **Step 5: Run complete blueprint tests and validator**

Run:

```powershell
C:\Users\alexn\Documents\Codex\.venvs\lrpr\Scripts\python.exe -m unittest discover -s playbooks\tests -p test_orchestrator_blueprint.py -v
C:\Users\alexn\Documents\Codex\.venvs\lrpr\Scripts\python.exe playbooks\scripts\validate_orchestrator_blueprint.py
```

Expected: All blueprint tests pass and validator prints
`Orchestrator blueprint contract passed.`

- [ ] **Step 6: Commit**

```powershell
git add playbooks/automated-orchestrator-blueprint/IMPLEMENTATION-ROADMAP.md playbooks/tests/test_orchestrator_blueprint.py
git commit -m "docs: add orchestrator implementation roadmap"
```

---

### Task 8: Deterministic Blueprint Packaging and Final Review

**Files:**
- Create: `playbooks/scripts/package_orchestrator_blueprint.py`
- Modify: `playbooks/tests/test_orchestrator_blueprint.py`
- Create: `outputs/Automated-Multi-Agent-Orchestrator-Blueprint.zip`
- Create: `outputs/Automated-Multi-Agent-Orchestrator-Architecture.md`

**Interfaces:**
- Consumes: Validated blueprint.
- Produces: Deterministic ZIP and standalone architecture document with SHA-256 hashes.

- [ ] **Step 1: Add failing packaging tests**

Add:

```python
    def test_package_script_is_deterministic_and_safe(self) -> None:
        script = (
            ROOT / "playbooks" / "scripts" / "package_orchestrator_blueprint.py"
        ).read_text(encoding="utf-8")
        self.assertIn("ZipInfo", script)
        self.assertIn("(1980, 1, 1, 0, 0, 0)", script)
        self.assertIn("validate", script)
        self.assertIn("outputs", script)
```

- [ ] **Step 2: Run tests and verify failure**

Run the Task 7 unittest command.

Expected: FAIL because the package script is absent.

- [ ] **Step 3: Implement deterministic packaging**

The standard-library script must:

- Validate before writing
- Delete only the exact prior blueprint ZIP/architecture outputs
- Copy `ARCHITECTURE.md` byte-for-byte to the standalone output
- Package `manifest.json` and every required file
- Use archive root `Automated-Multi-Agent-Orchestrator-Blueprint/`
- Use fixed ZIP timestamp `(1980, 1, 1, 0, 0, 0)`
- Reject absolute, parent-traversal, symlinked, or out-of-root sources
- Print ZIP and architecture SHA-256 hashes

- [ ] **Step 4: Run tests, validate, and package twice**

Run:

```powershell
C:\Users\alexn\Documents\Codex\.venvs\lrpr\Scripts\python.exe -m unittest discover -s playbooks\tests -p test_orchestrator_blueprint.py -v
C:\Users\alexn\Documents\Codex\.venvs\lrpr\Scripts\python.exe playbooks\scripts\validate_orchestrator_blueprint.py
C:\Users\alexn\Documents\Codex\.venvs\lrpr\Scripts\python.exe playbooks\scripts\package_orchestrator_blueprint.py
C:\Users\alexn\Documents\Codex\.venvs\lrpr\Scripts\python.exe playbooks\scripts\package_orchestrator_blueprint.py
```

Expected: Tests and validator pass; both packaging runs print identical hashes.

- [ ] **Step 5: Review the complete blueprint**

Give a fresh strong reviewer:

- Approved design specification
- This implementation plan
- Every blueprint source file and schema
- Test/validator output
- Archive listing and hashes

Require review of:

- Internal consistency
- Schema/document terminology alignment
- Threat and permission completeness
- Provider-neutrality
- Review/approval bypass resistance
- Budget/provider-failure behavior
- Roadmap feasibility
- Clear non-runnable scope

Fix Critical and Important findings with validation regressions, then re-review
until approved.

- [ ] **Step 6: Commit**

```powershell
git add playbooks/scripts/package_orchestrator_blueprint.py playbooks/tests/test_orchestrator_blueprint.py
git commit -m "build: package orchestrator architecture blueprint"
```
