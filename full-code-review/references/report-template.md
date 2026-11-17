# Report skeleton

Fill in every section. Start each section with its conclusion and its numbers, not with a description of the section.

```markdown
# <Project> — Code Review & Fix Plan

<date> · reviewed commit `<sha>` on `<branch>`

## Summary
**Verdict: <one sentence, e.g. "not ready for real payments or real customers">.** <N> launch-blocking issues; <M> let an attacker with no special access <worst outcomes>.

| Area | Headline | Blockers |
| --- | --- | --- |
| Security | ... | n |
| Privacy | ... | n |
| Architecture | ... | n |
| Code quality | ... | n |

How to read: Findings sections record what was found; the **Fixes** section is the action plan. "Confirmed" = re-read in a second pass; "Reported" = traced once. Nothing was executed.

## Scope & method
- What was reviewed: a table of area → paths, including secrets (tracked files and git history).
- How: five lenses (list them), with the evidence bar (attacker, input, missing control, result).
- Limits: read-only; linters that could not run; deployment facts not in the repo; this is a focused review, so a clean area is not proof of no defects.

## Findings: Security
<one-line lead: the worst 2–3 outcomes>
Severity scale: Critical / High / Medium / Low definitions.

**Code execution and server access**
| ID | Sev | Finding | Who | Where | Status | Fix |
**Payments and money** (same columns)
**Account takeover and authentication** (same columns)
**Paywall, ownership and content** (same columns)
Secrets result. **Checked and correct:** ...

## Findings: Privacy
<lead naming the biggest legal exposure and the law (DPDP 2023 / GDPR)>
| ID | Sev | Finding | Data | Where | Status | Fix |
**Missing privacy capabilities:** deletion, export, consent/notice, retention, processor duties.
**Done well:** ...

## Findings: Architecture & system design
<lead>
**As built:** 5 bullets: process model, layering, where work runs, state, schema.
| ID | Impact | Problem | Evidence | Fix |
**Done well:** patterns to copy.

## Findings: Code quality
<lead: confirmed bugs first, then size and duplication>
| ID | Type | Finding | Where | Status | Fix |
**Checked and fine:** ...

## Fixes
There are <N> fixes. P0 blocks launch, P1 next sprint, P2 privacy and architecture, P3 cleanup.

### Tracker
| Fix | Priority | Title | Closes | Effort |
Effort: XS < 1 h, S < 1 day, M 1–3 days, L > 3 days.

### How to use these fix specs with an AI coding assistant
A table of the spec parts, the paste-in prompt (from fix-spec-template.md), order and dependencies, and what "done" means (tests pass, rescan checks hold, tracker ticked).

**Corrections found while writing the specs.** Findings that changed, new issues, cross-dependencies.

### P0: Fix before launch
#### F-01 ... (full spec template)
### P1: Fix next sprint
### P2: Privacy compliance and architecture
### P3: Code-quality cleanup

## Open questions and rollout
| # | Question | Why it matters | Affects |
**Rollout order:** Day 1 / Week 1 / Week 2 / Weeks 3–4 / Ongoing; rotate secrets if a leak was possible.
**After P0 ships:** queries to detect past abuse or lost revenue.
```
