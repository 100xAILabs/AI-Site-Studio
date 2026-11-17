---
name: full-code-review
description: Full review of a codebase across four core domains (security split into auth & infra, privacy, architecture, code quality) that ends in a ranked findings report plus one self-contained, AI-ready fix spec per issue, written so a re-scan after fixing does not raise the same issue again. Supports transition to Phase 7 production remediation when requested. Use when asked to "review / audit / scan the whole codebase", "security and privacy review", "senior engineer / architect review", or "give me fixes another AI can implement".
---

# Full code review

Review a whole repository the way a senior engineer, a system architect, a security reviewer and a privacy engineer would, then turn every finding into a fix spec that a developer can paste into any AI coding assistant on its own.

The output is one report with these parts:

1. Summary
2. Scope and method
3. Findings: Security
4. Findings: Privacy
5. Findings: Architecture
6. Findings: Code quality
7. Fixes: tracker, how-to-use prompt, corrections, specs P0 to P3
8. Open questions and rollout

## Ground rules (apply in every phase)

- **Read-only.** Do not edit source, install dependencies, run the app, run builds, or make network calls to the system under review. `grep`, `find`, `cat`, `sed -n`, `wc` and `git log` are fine.
- **Never execute target code.** That includes `npm install`, test suites and build scripts. A malicious `package.json` or `setup.py` runs on install.
- **Evidence or it is not a finding.** Every finding names all of these, with `file:line`:
  - who can do it (anonymous visitor, any logged-in user, seller, admin, someone who can read the logs);
  - the input or action;
  - the control that is missing;
  - the concrete result.
- **No checklist noise.** Skip "best practice" items that have no reachable impact, and skip self-harm (a user hurting only themselves).
- **Unknown deployment facts are questions, not findings.** The production `.env`, proxy behaviour, origin layout and cloud settings go in *Open questions*, never assumed either way.
- **Fix the root cause, not the cited line.** Before writing a fix, grep for every copy, caller and sibling route with the same pattern. Every one goes in the spec's *Also fix* list.
- **Mark certainty.** *Confirmed* means the cited lines were re-read in a second pass. *Reported* means traced once. Never claim an exploit was run.

## Phase 1: Reconnaissance

1. Record the commit (`git log -1 --oneline`) and the branch. Every line number in the report refers to this commit.
2. Map the repo:
   - largest files:
     - POSIX: `git ls-files | xargs wc -l | sort -n | tail -60`
     - Windows PowerShell / Python: `python -c "import subprocess; files = subprocess.check_output(['git', 'ls-files']).decode().splitlines(); counts = [(sum(1 for _ in open(f, encoding='utf-8', errors='ignore')), f) for f in files if open(f, 'rb').read(1024)]; [print(f'{c:6d} {f}') for c, f in sorted(counts)[-60:]]"`
   - directory counts;
   - stack: README, `package.json`, `requirements.txt`/`pyproject.toml`, Dockerfile, compose, proxy config, CI files, docs/ADRs.
3. List the trust boundaries:
   - public routes and auth dependencies;
   - admin routes;
   - webhooks;
   - file upload and download;
   - anything that runs subprocesses, builds, git, or unzips;
   - user-generated HTML;
   - AI/LLM calls;
   - payments and payouts;
   - custom domains and TLS.
4. Look for committed secrets:
   - list `git ls-files` entries matching `.env`, `key`, `secret` or `.pem`;
   - grep the tracked files for key patterns (`sk_live`, `AKIA`, `-----BEGIN`, `api_key =`);
   - check `git log -p` for removed secrets if time allows.

## Phase 2: Five review lenses

Run each lens as an independent pass. If the IDE supports parallel agents, run them in parallel, one agent per lens, each with its narrow brief. Otherwise run them in sequence and finish one lens before starting the next. Use the checklists in `references/checklists.md` (located in the skill's `references/` directory).

| # | Lens | ID prefix | Covers |
| - | ---- | --------- | ------ |
| 1 | Security: auth and payments | S- | OAuth, JWT, OTP, ownership checks on every route, admin and payout routes, payment verification, webhooks, entitlements |
| 2 | Security: code execution, AI, deploy, infra | S- | file paths, subprocesses, untrusted builds, archives, SSRF, user HTML, paywall bypass, AI cost abuse, containers, TLS, secrets, insecure defaults |
| 3 | Privacy | P- | PII stored, logged, sent to third parties, over-exposed in APIs or front-end storage; deletion, export, consent, retention (DPDP Act 2023 for India, GDPR for EU users) |
| 4 | Architecture and system design | A- | layering, async correctness, long work in requests, migrations, state and scaling, config drift, indexes, tests/CI, observability, docs vs reality |
| 5 | Code quality | Q- | real bugs, missing deps, dead code, duplication, giant files (name the split seams), dependency hygiene, error handling, test quality |

Each lens returns a ranked list. Each item has: ID, severity, title, `file:line`, who, exploit or failure path in 2–4 sentences, smallest fix direction. Each lens also returns a short "checked and correct" list, because what is done well belongs in the report.

**Severity scale (security and privacy):**

| Severity | Meaning |
| -------- | ------- |
| Critical | An unauthenticated actor, or any user, gets code execution, all data, account takeover, or money. |
| High | An explicit control is fully defeated with real consequences. |
| Medium | A real violation with limited reach or uncommon preconditions. |
| Low | Minor impact. |

Architecture and quality use an impact rating (High / Medium / Low) instead.

## Phase 3: Verify

For every Critical and High finding, re-open the cited lines and trace the path end to end, including the auth dependency, the decorator, and the actual SQL filter. Then mark the result:

- the finding holds: mark it *Confirmed*;
- the code differs: correct the finding;
- it is wrong: drop it.

Look for siblings while you are there. These verification passes regularly find issues that are worse than first reported.

## Phase 4: Write the findings report

Use the skeleton in `references/report-template.md`. Group the security findings by theme:

- code execution and server access;
- payments and money;
- account takeover and authentication;
- paywall, ownership and content.

Each findings table has these columns: `ID | Sev | Finding | Who | Where | Status | Fix`. The Fix column is the fix ID.

## Phase 5: Fix specs (the most important output)

Every finding maps to a fix ID (F-01, F-02, …). One fix may close several findings. Assign priority:

- **P0:** blocks launch: any Critical, anything that moves money, account takeover, code execution.
- **P1:** the remaining High findings and the serious privacy items. Fix within a sprint.
- **P2:** privacy compliance and architecture.
- **P3:** code-quality cleanup.

Write each fix with the exact template in `references/fix-spec-template.md`, after reading the real source again for that fix. Each spec must stand alone: a developer will paste one spec, with the prompt from `references/fix-spec-template.md`, into an AI assistant that has no other context. Non-negotiables:

- **Current code:** a verbatim excerpt with `path:start-end`.
- **Required behaviour:** testable MUST / MUST NOT rules. A re-scan checks exactly these.
- **Also fix:** every other location found by grep, or "None found (grep: `pattern`)".
- **Rescan checks:** commands with expected output, e.g. `grep -rn "npm.*install" src` → every hit contains `--ignore-scripts`.
- **Tests:** test file, test names and assertions, using the repo's existing fixtures (read `conftest.py` or the test setup first).
- Note cross-dependencies between fixes, e.g. "F-22 must call F-13's helper".

If writing a spec reveals that a finding was wrong or incomplete, update the finding. Also add a short *Corrections found while writing the specs* list under the Fixes heading.

Add a tracker table at the top of Fixes, with these columns: `Fix | Priority | Title | Closes | Effort (XS<1h, S<1d, M 1–3d, L>3d)`.

## Phase 6: Open questions and rollout

- **Open questions:** a table of deployment facts only the operator can confirm. Each row says why the answer matters and which findings it affects.
- **Rollout:**
  - Day 1: the one-line P0 fixes.
  - Week 1: the rest of P0.
  - Week 2: P1, with CI started so every fix lands with its test.
  - Then P2 and P3.
  - If a secret-leak finding exists, include "rotate every secret after the leak fix".
  - Add a post-fix audit step: look for past abuse in data, such as orders completed without a captured payment.

## Delivery

- Write the report as Markdown, by default to `docs/code-review/REVIEW-<date>.md` unless the user names a place. Keep one fix spec per `####` heading so it can be copied out alone.
- Lead the summary with the verdict in one sentence, e.g. "Not ready for real payments", then a 4-row table: area → headline → blocker count.
- In chat, give a short ranked summary of the fix-now items with `file:line`, and say what still needs operator confirmation.
- Never paste secrets you find into the report. Cite the file and line, and recommend rotation.

## Quality bar before you finish

- Every Critical and High finding is *Confirmed*, or explicitly marked otherwise.
- Every finding has a fix ID, and every fix ID appears in the tracker.
- Every spec has all ten parts: header line, Context, Current code, Problem, Required behaviour, Implementation, Also fix, Tests to add, Rescan checks, Do not.
- No spec says only "add validation" or "improve security". Each names the function, the condition and the code.
- No finding relies on an assumed deployment fact.

## Phase 7: Production Remediation & Verification (When Requested)

When explicitly requested by the user to fix findings and prepare the repository for production:

1. **Order of Execution:** Apply fixes in order of priority:
   - **P0:** Critical security flaws, money theft, unauthenticated RCE, paywall bypasses.
   - **P1:** High-severity security, authentication takeover, privacy leaks, and data protection.
   - **P2:** Concurrency, event loop unblocking, and multi-worker cache distribution.
   - **P3:** Code-quality cleanup, input bounding, and rate-limiting.
2. **Implementation Standards:**
   - Satisfy every `MUST` / `MUST NOT` in the fix spec.
   - Apply fixes to all cited locations and files identified in *Also fix*.
   - Never introduce regressions or change unrelated interfaces.
3. **Automated Verification:**
   - Run compilation on all backend code: `python -m compileall -q backend/app backend/tests`.
   - Run frontend build to verify bundling: `npm --prefix frontend run build`.
   - Run each rescan check command defined in the fix specs (e.g., verifying zero matches for removed vulnerabilities).
4. **Update the Audit Documentation:**
   - Update `docs/code-review/REVIEW-<date>.md` with the verified resolution status in the Tracker.
   - Note any code corrections or findings discovered during remediation.
