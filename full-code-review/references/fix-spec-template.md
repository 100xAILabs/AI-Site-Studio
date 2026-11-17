# Fix spec template

Write one spec per fix, using exactly this structure. The spec must be understandable with no other context: a developer pastes it, together with the prompt at the bottom of this file, into Claude, Gemini, Cursor or Copilot.

Length: 2,000–5,000 characters per fix. Be precise rather than wordy. Long *Also fix* lists are fine; they are what stop a re-scan from finding the same issue again.

````markdown
#### F-XX: <imperative title, e.g. "Bind Razorpay verification to the stored order">

**Priority:** P0 · **Closes:** S-08, P-05 · **Severity:** Critical · **Effort:** S

**Context.** 1–3 sentences: what the feature is, and which files and functions it lives in.

**Current code** (`backend/app/api/v1/routes/payment.py:452-499`):
```python
<verbatim excerpt, max ~25 lines, trimmed with "# ..." where needed>
```

**Problem.** The concrete failure or attack, step by step. Say who can do it (anonymous, any user, seller, log reader) and what they get.
1. Attacker pays for the cheapest item and keeps the signature triple.
2. Sends it to `/payment/verify` with `order_id` = an expensive order.
3. The order completes; this repeats without limit.

**Required behaviour.**
- MUST compare `data.gateway_order_id` with the `Payment.gateway_order_id` stored for `data.order_id`.
- MUST reject orders that are not `PENDING` (409).
- MUST NOT create a `Payment` row from client-supplied IDs.
(Testable rules only. A re-review checks exactly these.)

**Implementation.**
1. In `verify_payment` (`payment.py:440`), load the payment by `order_id` AND `gateway_order_id` ...
```python
<target code: concrete and pasteable, not pseudo-code>
```
2. Add a unique constraint on `payments.gateway_payment_id` (new migration after head `<rev>`).

**Also fix.** Every other location with the same pattern:
- `payment.py:503-512` (mock branch: same missing binding)
- `subscriptions.py:120` ...
or "None found (grep: `<pattern>`)".

**Tests to add.** `backend/tests/test_payment_verify.py`:
- `test_signature_from_other_order_rejected`: create orders A and B; verify A; send A's triple with `order_id=B` → 400; B stays `PENDING`.
- `test_replay_same_order_rejected` → 409.
Use the existing fixtures: `<names from conftest.py>`.

**Rescan checks.**
- `grep -n "gateway_order_id" backend/app/api/v1/routes/payment.py` → the verify path compares against the stored value.
- `pytest backend/tests/test_payment_verify.py` passes.

**Do not.** What must keep working, and traps to avoid. For example: do not break the mock flow used by local tests; do not fulfil before the commit.
````

Rules:
- Re-read the source for each fix before writing it. If the finding turns out wrong or bigger than reported, add a line `**Reviewer note.** ...` after the header line.
- Line numbers refer to the reviewed commit. Say so once in the report, and quote enough code that the excerpt can be found again after lines shift.
- Use only `####` for fix headings, so each spec can be copied out alone.
- Put a fenced code block inside a numbered step only if the next step starts on a new line after a blank line. Otherwise some Markdown renderers merge the steps into one paragraph.

## Prompt to paste with each spec (include this in the report)

```text
You are working in the <PROJECT> repository (<stack summary>).
Implement the fix spec below exactly.

Rules:
1. Read every file named in the spec before editing. Line numbers are from commit <SHA> and may have shifted; locate code by the quoted excerpt.
2. Satisfy every MUST / MUST NOT under "Required behaviour". Apply the change to every location under "Also fix" as well.
3. Make the smallest change that meets the spec. Do not refactor unrelated code.
4. Add the tests under "Tests to add" and run them; run the full test suite.
5. Run every command under "Rescan checks" and confirm each expected result.
6. If the code differs from the spec so that a step cannot apply, stop and report the difference instead of guessing.
7. Finish with: files changed, tests added, test results, and the output of each rescan check.

--- FIX SPEC ---
<paste one F-XX section here>
```
