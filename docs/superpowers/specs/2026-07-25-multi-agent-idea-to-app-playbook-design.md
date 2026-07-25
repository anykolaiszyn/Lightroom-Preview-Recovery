# Multi-Agent Idea-to-App Playbook Design

Date: 2026-07-25

## Purpose

Create a reusable system that reproduces the successful development experience
used for the Lightroom Preview Recovery utility across future technical
projects.

The system must work across Codex, Claude Code, Ollama, and agents that can
follow a generic file-and-prompt protocol. It must preserve project state
outside chat history, route work according to risk and cost, use independent
review gates, and remain understandable to a person who wants to supervise
rather than manually manage every coding step.

The deliverable covers:

- Web, desktop, mobile, CLI, and API applications
- Automations and internal utilities
- Data pipelines
- AI-powered tools and agent applications
- Plugins and developer tooling

Research-only projects, business reports, presentations, and other
non-technical deliverables are outside the primary scope. The workflow may
still inspire those projects, but its quality gates are designed for technical
builds.

## Deliverables

The work produces two separate deliverables.

### Deliverable A: Hybrid Multi-Agent Starter Kit

The starter kit is immediately usable without building an orchestration
application.

```text
Multi-Agent-Idea-to-App/
├── HANDBOOK.md
├── QUICKSTART.md
├── prompts/
│   ├── 01-discovery.md
│   ├── 02-design.md
│   ├── 03-implementation-plan.md
│   ├── 04-task-implementation.md
│   ├── 05-task-review.md
│   ├── 06-integration.md
│   ├── 07-release.md
│   └── 08-handoff-and-resume.md
├── templates/
│   ├── AGENTS.md
│   ├── PROJECT-BRIEF.md
│   ├── DESIGN-SPEC.md
│   ├── IMPLEMENTATION-PLAN.md
│   ├── TASK-BRIEF.md
│   ├── IMPLEMENTATION-REPORT.md
│   ├── REVIEW-REPORT.md
│   ├── PROGRESS-LEDGER.md
│   └── RELEASE-CHECKLIST.md
├── adapters/
│   ├── CODEX.md
│   ├── CLAUDE-CODE.md
│   ├── OLLAMA.md
│   └── GENERIC-AGENT.md
└── examples/
    └── idea-to-app-example.md
```

### Deliverable B: Automated Orchestration Framework Blueprint

The blueprint describes a future automation system. It remains separate from
the starter kit so the proven workflow does not depend on experimental
orchestration code.

```text
Automated-Orchestrator-Blueprint/
├── ARCHITECTURE.md
├── AGENT-ROUTING.md
├── SECURITY-AND-PERMISSIONS.md
├── STATE-MODEL.md
├── PROVIDER-ADAPTERS.md
├── HUMAN-APPROVAL-GATES.md
├── OBSERVABILITY-AND-COSTS.md
├── IMPLEMENTATION-ROADMAP.md
└── schemas/
    ├── project-state.schema.json
    ├── task.schema.json
    └── review.schema.json
```

The blueprint includes schemas and interface contracts but no runnable
orchestrator implementation.

## Primary Operating Model

The starter kit uses an orchestrated workflow with human checkpoints.

One lead agent coordinates the project, delegates bounded tasks, and maintains
durable state. Routine work may proceed without repeated approval, but the
workflow pauses for approval at design, implementation planning, material
scope changes, risky external actions, and release.

```text
Idea
  -> Discovery
  -> Options
  -> Approved design
  -> Implementation plan
  -> Task implementation/review loop
  -> Integration
  -> Real-world validation
  -> Release review
  -> Packaged result
  -> Handoff
```

Chat history is supporting context, not the source of truth. Project files
record the authoritative goal, design, plan, progress, evidence, and open
findings.

## Agent Roles

### Lead Orchestrator

Preferred tools: Codex or Claude Code.

Responsibilities:

- Maintain the objective and active project state
- Confirm prerequisites and safety boundaries
- Produce or coordinate the design and plan
- Create bounded task briefs
- Select agents according to risk, capability, cost, and context
- Determine which tasks are safe to run concurrently
- Integrate only independently approved work
- Maintain the progress ledger
- Stop when new authority or a material user decision is required

The lead must not be the sole reviewer of its own high-risk implementation.

### Architect

Preferred tools: Codex or Claude Code.

Responsibilities:

- Explore the problem and available inputs
- Present multiple viable approaches and tradeoffs
- Define architecture, interfaces, data flow, safety boundaries, testing, and
  acceptance criteria
- Reduce unnecessary scope
- Write the approved design specification

Implementation does not begin until the written design is approved.

### Implementer

Eligible tools: Codex, Claude Code, Ollama, or a generic coding agent.

Responsibilities:

- Work only from an approved task brief
- Own explicitly named files or modules
- Inspect the existing implementation before editing
- Start with a failing test or other explicit red-state evidence
- Make the smallest robust scoped change
- Run focused and relevant full tests
- Produce an implementation report
- Avoid reverting or overwriting other agents' work

### Independent Reviewer

The reviewer must be a different agent from the implementer.

Responsibilities:

- Compare the implementation with the task brief and overall design
- Inspect the actual diff and relevant surrounding code
- Run focused tests or probes where useful
- Report findings as Critical, Important, or Minor
- Avoid editing during the review
- Approve only when no Critical or Important finding remains

### Local Supporting Agent

Preferred tool: Ollama.

Suitable work:

- Codebase exploration
- File and dependency inventories
- Routine fixtures
- Straightforward unit tests
- Documentation drafts
- Summaries and handoffs
- Preliminary static review
- Low-risk mechanical changes with narrow ownership

Ollama does not independently approve:

- Authentication or authorization
- Secrets, encryption, or personal data handling
- Destructive database or filesystem operations
- Payments
- Concurrency, cancellation, or recovery semantics
- Deployment and infrastructure
- Packaging and licensing
- Final release

### Release Reviewer

Preferred tool: the strongest available independent cloud agent.

Responsibilities:

- Review the accumulated implementation rather than only the latest patch
- Reconcile every acceptance criterion with current evidence
- Verify security, dependencies, licensing, and package contents
- Run or inspect the packaged-artifact smoke test
- Confirm real-input safety
- Reject stale or incomplete verification

## Project State Model

Every participating agent reads the shared control files before acting:

```text
AGENTS.md
PROJECT-BRIEF.md
DESIGN-SPEC.md
IMPLEMENTATION-PLAN.md
PROGRESS-LEDGER.md
```

For a bounded task, the agent also reads:

```text
tasks/<task-id>/TASK-BRIEF.md
tasks/<task-id>/IMPLEMENTATION-REPORT.md
tasks/<task-id>/REVIEW-REPORT.md
```

The progress ledger identifies:

- Current lifecycle phase
- Active task
- Completed and pending tasks
- Dependencies
- Assigned agent and file ownership
- Review status
- Open findings
- Latest verification evidence
- Blockers and required decisions

Only the lead orchestrator changes which task is active. Implementers and
reviewers update their reports, while the lead reconciles those reports into
the ledger.

## Cross-Tool Handoff Contract

Each agent finishes with a structured report containing:

- Task identifier and status
- Files owned and changed
- Behavioral changes
- Commands and tests executed
- Exact results
- Assumptions
- Risks and unresolved findings
- Commit, branch, worktree, or patch identifier
- Recommended next action

The next agent receives this standard launch instruction:

```text
Read the project control files before acting. Treat them as authoritative over
chat history. Inspect the current working tree and do not discard uncommitted
changes. Resume only the task marked active in PROGRESS-LEDGER.md. Follow its
ownership, testing, safety, and review requirements. Update the ledger and
produce the required report before stopping.
```

Tool adapters translate the shared protocol into the smallest durable
instruction surface supported by each environment:

- Codex: repository `AGENTS.md`, task prompt, skills where useful, and isolated
  worktrees for concurrent coding
- Claude Code: repository guidance and task-scoped agent prompts
- Ollama: explicit context bundle, bounded prompt, allowed files, and command
  wrapper
- Generic agent: a self-contained task brief plus the shared control files

Adapters must not change the lifecycle or quality standard.

## Development Lifecycle

### Phase 1: Discovery

Goals:

- Understand the real problem and intended user
- Inspect existing code, inputs, data, tools, and constraints
- Identify high-risk operations
- Establish what success means

Outputs:

- `PROJECT-BRIEF.md`
- Read-only evidence and inventories
- Open questions

### Phase 2: Options and Design

Goals:

- Present two or three viable approaches
- Explain tradeoffs and recommend one
- Define scope, architecture, components, data flow, failure handling, safety,
  testing, packaging, and acceptance criteria

Output:

- Approved `DESIGN-SPEC.md`

### Phase 3: Implementation Planning

Goals:

- Split the design into small dependency-aware tasks
- Define file ownership and interfaces
- Specify red/green tests, verification commands, and review criteria
- Identify independent tasks that may safely run concurrently

Output:

- Approved `IMPLEMENTATION-PLAN.md`

### Phase 4: Task Loop

For each task:

1. Lead writes `TASK-BRIEF.md`.
2. Implementer records a red state.
3. Implementer makes the scoped change.
4. Focused tests pass.
5. Relevant full tests pass.
6. Implementer writes `IMPLEMENTATION-REPORT.md`.
7. Independent reviewer inspects the diff and evidence.
8. Critical and Important findings return to the implementer.
9. Fixes receive regression tests.
10. The same reviewer rechecks the corrected result.
11. Lead marks the task complete only after approval.

### Phase 5: Integration

Goals:

- Combine approved components
- Validate interfaces and shared assumptions
- Run integration and end-to-end tests
- Resolve cross-task findings

### Phase 6: Real-World Validation

Goals:

- Test against real or production-like inputs
- Keep source inputs immutable where required
- Bound external effects
- Compare before/after state
- Preserve audit evidence

### Phase 7: Release

Required evidence:

- Fresh full test suite
- Security and dependency review
- License and package inventory
- Package-content scan
- Packaged-artifact startup test
- Bounded end-to-end smoke test
- Output/report reconciliation
- Independent final review

### Phase 8: Handoff

Goals:

- Leave a durable resume point
- Record exact artifact locations and hashes
- Explain known limitations
- Preserve uncommitted work and local-only state safely

## Human Approval Gates

Human approval is mandatory after:

1. The written design specification
2. The implementation plan
3. A material scope expansion or architecture change
4. A destructive or externally consequential action
5. A change to security, privacy, licensing, or deployment assumptions
6. Final release readiness

Routine task implementation and review may proceed autonomously between gates.

## Parallel Work Rules

Parallel execution is allowed only when:

- Tasks have no unresolved dependency on each other
- File ownership does not overlap
- Shared schemas or interfaces are already approved
- Agents are told they are not alone in the codebase
- Each agent is instructed not to revert others
- The lead remains responsible for integration

If two tasks touch the same module or one depends on the other's design
decision, they run sequentially.

## Quality Gates

Every task must satisfy:

1. Complete task brief
2. Demonstrated red state
3. Focused green tests
4. Relevant full-suite green tests
5. Independent review
6. Regression tests for Critical and Important findings
7. Reviewer approval
8. Progress-ledger evidence

Release additionally requires the Phase 7 evidence.

Previous passing tests are not sufficient for a release claim. Verification
must be rerun after the final source state and package are produced.

## Risk Routing

The lead scores work using:

- Destructive potential
- Security and privacy impact
- External side effects
- Concurrency complexity
- Data sensitivity
- Reversibility
- Release impact

High-risk tasks go to a strong cloud implementer and a separate strong
reviewer. Low-risk, bounded work may go to Ollama.

## Cost Controls

- Use Ollama for exploration, summaries, fixtures, documentation, and
  low-risk first passes
- Use balanced Codex or Claude models for ordinary implementation
- Reserve strongest models for architecture, unsafe I/O, concurrency,
  security, packaging, and final review
- Run focused tests before expensive full suites
- Parallelize only independent work
- Send agents the smallest relevant context bundle
- Prefer durable files over repeatedly replaying chat history
- Stop review loops after clean evidence-backed approval
- Track provider/model usage in the ledger when budgets matter

## Automated Orchestrator Blueprint

The future orchestrator contains:

```text
Project controller
├── State store
├── Task scheduler
├── Agent router
│   ├── Codex adapter
│   ├── Claude Code adapter
│   ├── Ollama adapter
│   └── Generic command adapter
├── Permission broker
├── Review gate
├── Evidence collector
├── Cost and usage tracker
└── Human approval interface
```

### Controller

Owns lifecycle state, dependencies, active tasks, and integration decisions.

### State Store

Persists project, task, review, artifact, approval, and cost records. The
blueprint favors an append-only event trail plus materialized current state.

### Scheduler

Selects dependency-ready work and permits concurrency only when ownership and
interface rules allow it.

### Agent Router

Chooses a provider and model using:

- Required capability
- Risk classification
- Context size
- Latency preference
- Cost budget
- Local/offline requirement
- Provider availability

### Permission Broker

Provides task-scoped filesystem, command, network, credential, and external
action permissions. Agents cannot expand their own authority.

### Review Gate

Requires a distinct reviewer identity and blocks integration while Critical or
Important findings remain open.

### Evidence Collector

Captures prompts, selected context, patches, commands, tests, reports, package
hashes, and approval decisions without storing secrets.

### Human Approval Interface

Presents decisions at the mandatory gates and supports approve, revise, or
stop outcomes.

## Automated Orchestrator Safety

- Providers receive only task-relevant files
- Secrets never enter prompts, reports, or logs
- External actions use least privilege
- Destructive actions require explicit approval
- Agent ownership is enforced
- Implementers cannot approve their own work
- The audit trail is append-only
- Interrupted tasks remain resumable and incomplete
- Model or provider failure cannot silently skip a gate
- Budget exhaustion pauses rather than degrading release requirements

## Automated Orchestrator Schemas

The blueprint supplies JSON Schemas for:

- Project state
- Task definitions and dependency/ownership data
- Review findings, dispositions, and approval state

Schemas validate state exchange between provider adapters. They do not encode
provider-specific prompt formats.

## Orchestrator Implementation Roadmap

1. File-backed single-project controller
2. Ollama adapter
3. One cloud-provider adapter
4. Task scheduler and ownership enforcement
5. Evidence and review gates
6. Human approval interface
7. Cost and usage tracking
8. Additional provider adapters
9. Isolated worktree execution
10. Recovery, audit export, and release hardening

Each stage requires its own design, tests, threat review, and release gate.

## Acceptance Criteria

The completed starter kit must:

- Be understandable without reading the Lightroom project conversation
- Support Codex, Claude Code, Ollama, and a generic agent
- Include ready-to-copy prompts for every lifecycle phase
- Include complete editable templates for every shared control artifact
- Explain agent roles, ownership, review independence, and risk routing
- Explain how to pause, resume, and switch tools safely
- Include a worked idea-to-app example
- Include a short quickstart and a comprehensive handbook
- Keep the automated framework clearly separate

The completed blueprint must:

- Define components, interfaces, state, routing, permissions, approvals,
  evidence, costs, and failure recovery
- Include valid JSON Schemas for projects, tasks, and reviews
- Provide a staged implementation roadmap
- Avoid pretending that a runnable orchestrator already exists

## Official Product Context

OpenAI currently positions Work for long, multi-step knowledge work and finished
deliverables, while Codex remains focused on software development, repository
work, commands, testing, and review:

https://help.openai.com/en/articles/20001275/

Codex documentation exposes `AGENTS.md` and subagents as agent-configuration
surfaces:

https://learn.chatgpt.com/docs/customization/overview

The starter kit remains tool-neutral. These references inform the Codex
adapter only.

