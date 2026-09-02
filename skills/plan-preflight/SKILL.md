---
name: plan-preflight
description: >
  Close the question "is this plan ready to implement?" with a binary PASS/FAIL
  verdict. Two reviewers — Claude plus an optional codex second voice (degrades
  to single-reviewer automatically) — examine a plan document independently,
  auto-fix contract-level defects only, and re-review until the gate closes.
  Locked policy decisions are never changed. Target file (.md/.html/.txt)
  must be specified. Use when the user points at a plan, design document, or
  proposal and asks to review, vet, gate, validate, or find gaps before
  implementation starts — "gate this plan", "any holes in this design?",
  "is this ready to build?". Do not substitute a one-shot inline review; the
  convergence loop beats a single pass. Not a code review tool — PRs, diffs,
  and implemented code are out of scope; this gate closes pre-implementation
  plan/design documents only.
allowed-tools:
  - Read
  - Edit
  - Write
  - Grep
  - Glob
  - Bash
  - Agent
  - AskUserQuestion
---

# plan-preflight

A review loop that drives one plan document (or a companion-document set) to a
binary **GATE verdict: PASS or FAIL**. The skill carries the framing — review
altitude, policy invariants, finding schema — so you never re-type it.
Invocation is one line.

## Why this design

Two failure modes make naive "review my plan" loops run forever. plan-preflight
exists to neutralize both.

**Trap 1 — the bar slips from plan to spec.** Point a strong reviewer at a
*plan* and its bar drifts toward *implementation spec*: it starts demanding
poll intervals, HTTP status codes, exact endpoint paths. Since a plan
legitimately defers those, PASS becomes asymptotic — every round finds new
"missing detail" that was never the plan's job. The gate therefore **pins the
review altitude to plan level** in every prompt: contracts, decisions, and
schema completeness are judged; implementation micro-detail is explicitly not
a failing reason.

**Trap 2 — reviewers avoid reporting empty-handed.** A cold reviewer told to
"report defects" will manufacture medium-grade findings rather than return
nothing, so round counts balloon. In practice, genuine defects converge within
1–2 rounds. The gate therefore ① tells reviewers that **zero findings is a
normal, expected outcome**, ② applies a **severity gate** (only critical/high
contract defects extend the loop), and ③ attaches the **prior-round
disposition history** so already-handled findings cannot be re-reported.

## Guarantees

- Locked policy decisions are reported on, never modified.
- Nothing outside the target plan file(s) is edited — and reviewers themselves
  edit nothing; only the orchestrator applies fixes.
- A restore point (`<file>.pre-gate-<UTCstamp>`) is created before any edit.
- The gate never commits, pushes, or deploys. Final approval belongs to the user.

## Scope

The core (dual-voice review loop + scope filter + auto-fix) is **format- and
project-agnostic**. Targets can be `.md`, `.html`, `.txt` — anything readable;
reviewers read content, not extensions. Project-specific helpers (e.g., a plan
validation script) are used when present and silently skipped when absent —
their absence never blocks the gate.

## Invocation

```
/plan-preflight <plan-path> [options]
```

- `<plan-path>` (**required**) — the plan file. Companion documents are
  comma-separated: `a.md,b.md`. No auto-detection: if omitted, ask once for
  the path (guessing risks gating the wrong document). Everything else —
  altitude, invariants, checklist — is never asked about.
- `--invariants <file|"inline">` — source of locked policy. Default:
  auto-collected in Step 0.
- `--codex on|off|auto` (default `auto`) — second reviewer. `auto` = dual-voice
  when the `codex:codex-rescue` agent is available, single-voice otherwise.
- `--codex-mode rescue|adversarial` (default `rescue`) — depth of the second
  voice. `adversarial` adds contract-breaking framing for high-risk plans.
- `--base N` (default 3) / `--max M` (default 5) — base round count / extended
  cap when critical/high defects persist.
- `--log <file>` — round log location. Default: `<plan>.review.md`.

**Report language.** The Step 3 report to the user, and the `--log` file, are
written in whatever language the user's invocation was in (or explicitly
requested) — default English if no signal. **Everything reviewer-facing is
fixed English — not just the Step 0 prompt templates but every message sent
to a reviewer across the whole gate: round 2+ dispatches, prior-round
disposition blocks, nudges/recalls, and any SendMessage follow-up.** The
templates were tuned in English, and non-English reviewer input makes
CLI-backed reviewers (Codex) drift into third-language reasoning (observed:
Korean prompts → Japanese chain-of-thought in shell logs). Only the
orchestrator's user-facing report and log adapt.

## Core principles

Injected into every reviewer prompt, every round:

1. **Plan-level altitude.** The verdict criterion is completeness of
   **contracts, decisions, and schemas**. Implementation micro-detail — poll
   intervals, timeouts, HTTP codes, exact endpoint or file path strings, copy
   text, hash algorithm choice — is "settled at implementation time" and is
   **not a failing reason**. Do not drill on it.
2. **Locked policy = out of scope.** Proposals to change collected invariants
   (redefining the problem, expanding/shrinking scope, reversing decisions)
   are **reported but never applied**. Only a security or feasibility blocker
   may be surfaced, explicitly labeled "policy-change proposal (out of scope)".
3. **Auto-fix contract defects only.** Applied fixes are limited to
   contract-level findings: core domain contracts (concurrency, idempotency,
   state transitions, rollback, interface boundaries — as fits the plan's
   domain), cross-document contradictions, mismatches with cited code facts,
   and unresolved-but-unmarked gaps. Policy and impl-micro are never edited.

## Procedure

### Step 0 — Lock the target, build the prompts

1. **Target = the specified `<plan-path>`.** Verify existence. Format does not
   matter — reviewers read content.
2. **Optional pre-validation.** If the project ships a plan validation script
   and the target matches its format, run it; on failure, tell the user and
   confirm whether to continue. Otherwise skip silently.
3. **Restore point.** Copy each target to `<file>.pre-gate-<UTCstamp>`
   (`date -u +%Y%m%dT%H%M%SZ`).
4. **Analyze the file and its directory** — the prompt material. The specified
   file is the anchor; its surroundings complete the picture:
   - **Companion documents.** If the target is part of an A/B pair in the same
     directory, or its body links (`href`/relative path) to a status page,
     shared plan, or brief, pull those in as co-review targets
     (cross-document consistency). Also look for brief/invariant/status files
     in the directory and its parent.
   - **Locked policy (scope-out list).** Collect in priority order:
     (a) `--invariants` → (b) "locked/decided policy" sections of the
     companion/brief documents → (c) "do not change / locked / decided"
     sections in the target body → (d) failing all, treat the target's
     "Decisions" section as no-relitigation. → `<collected invariants>`.
   - **Code citations.** Extract file/line/function citations from the target
     (and companions) into `<code fact citations>`; verify cited files exist
     at the cited paths. A grep like the following seeds the list:
     ```bash
     grep -ohE '[A-Za-z0-9_/.]+\.[a-z]{1,4}[: ]*[0-9]+|[A-Za-z_][A-Za-z0-9_]*\(\)|`[^`]+`' <target> | sort -u | head -60
     ```
   - **Review focus.** From the body, derive ⓐ what the plan is about
     (1–3 lines), ⓑ the key contracts/decisions it claims, ⓒ the risks and
     open questions it admits → `<plan-specific review focus>`. A payments
     plan gets transactions/duplicate-charge focus; a migration plan gets
     rollback/data-loss; a UI plan gets state/rendering — **it differs per
     plan, every time.**
5. **Assemble the two prompts.** Fill the placeholders of the reviewer prompt
   templates below with the Step 0.4 output, producing `REVIEW_PROMPT_PRIMARY`
   and `REVIEW_PROMPT_CODEX` (same body; the codex variant adds one
   filesystem-boundary line, plus one adversarial line when
   `--codex-mode adversarial`). Assemble **once and reuse across all rounds** —
   invariants, focus, and citations are properties of the plan, not the round;
   only the document body reviewers read changes between rounds. Announce a
   one-line summary (`Focus: …`) and enter the loop.

   > Prompts are **not static**. [Fixed framing: altitude, scope-out, output
   > schema] + [what Step 0.4 extracted: invariants, companions, citations,
   > focus] + the document body are actually assembled here. A different plan
   > yields a different prompt.

### Step 1 — Resolve the second reviewer

The second voice is **only** the `codex:codex-rescue` agent (from the
openai-codex plugin), invoked via the Agent tool. (`--codex off` skips it.)

1. If the agent type is available in this environment → dual-voice.
2. Otherwise → single-voice (`[primary-only]`), one-line notice. **Do not fall
   back to a raw `codex` CLI** — `codex exec` hangs often enough to stall the
   gate; the omission is deliberate.
3. If an agent call fails or times out mid-run, finish that round single-voice
   and tag `[codex-degraded]`.
4. **An empty reply is a failure, not a vote.** The rescue agent returns
   nothing when the Codex call cannot be made. Treat an empty reply, or any
   reply without a `VERDICT:` line, as `[codex-degraded]` — never as "zero
   findings + PASS".
5. **Pin the routing.** The rescue agent is a forwarder that picks execution
   mode and sandbox from the request text: it runs long-looking tasks in the
   background (then the reply is only a job id, not findings), adds `--write`
   unless the request reads as review-only, and resumes the previous Codex
   session when the text sounds like a follow-up. So every codex dispatch
   must (a) start with the routing tokens `--wait --fresh` (foreground, new
   session — the forwarder strips them from the task text), and (b) state
   plainly that it is a read-only review with no file edits, so the run stays
   in the read-only sandbox.

> Agent presence does not guarantee a working call: the underlying Codex CLI
> must be installed **and authenticated** (`codex login` or `OPENAI_API_KEY`).
> An unauthenticated CLI surfaces as a call failure — rule 3 handles it; do
> not stall the gate retrying, and mention the likely cause ("codex not
> logged in?") in the one-line notice.

### Step 2 — The round loop

`round = 1`, `cap = base (3)`:

1. **Dispatch.** Use the Step 0.5 prompts as-is. With a second voice, launch
   **both reviewers in the same message** (parallel); otherwise just the
   primary. Primary = a **fresh Agent subagent** (`subagent_type:
   "general-purpose"` — never `fork`, which inherits this conversation's
   context; cold and independent; `REVIEW_PROMPT_PRIMARY`). Second =
   `codex:codex-rescue` (`REVIEW_PROMPT_CODEX`, prefixed with `--wait --fresh`
   per Step 1.5). Both see the **same current document**, and neither edits
   anything — the orchestrator alone applies fixes in step 3.
2. **Collect and classify** each finding:
   `{title, file, severity, isContractLevel, isPolicyChange, isImplMicro,
   rationale}`. `isPolicyChange` or `isImplMicro` → **reject** (log "out of
   scope", no edit). Remaining `isContractLevel` → accept.
   - **Dup filter:** findings substantially identical to one already rejected
     or already fixed in a prior round do not count as new (`[dup]` in the
     log, excluded from the verdict).
3. **Auto-fix** accepted findings only, via Edit, in the plan document. One
   log line per fix (file · what · why). Never touch invariants or impl-micro.
   If a finding is ambiguous (could be policy), do not fix — surface it as
   "needs confirmation".
4. **Round verdict (severity gate).** If this round's accepted findings
   (post-dup-filter) contain **zero critical/high → GATE PASS, stop.**
   - Medium-only: apply the fixes but **do not run a re-check round — PASS
     immediately** (`[pass-with-notes]` tag + the medium list in the log).
     By definition, medium does not block starting implementation.
   - Reviewer verdicts are advisory; the orchestrator decides. Even on a
     reviewer FAIL, if every cited reason is medium, impl-micro, or policy,
     **override to PASS** (one-line rationale in the log). Only real
     critical/high contract defects increment the round.
5. **Cap.** If `round > cap` without PASS (= critical/high persists): if `cap`
   was `base`, extend to `max (5)` and continue. If `round > max`, stop with
   **GATE FAIL** and the list of unresolved contract defects.
6. **Round 2+ prompt augmentation.** Append the **prior-round disposition
   block** (accepted-and-fixed list / rejected-out-of-scope list) to the
   fixed prompt before dispatch — this blocks re-reports and re-drilling of
   already-rejected altitude. Write the block and the whole dispatch in
   English, even when the user-facing report language is not English (see
   "Report language").
7. End every round with one line:
   `[PROGRESS] R{n}: accepted X (crit/high A · med B) · rejected Y · dup Z · verdict …`

> Rounds are **sequential** (each must see the previous round's edited
> document). "Parallel" means the two voices *within* a round. Never let the
> two reviewers edit the same file on independent tracks (conflicts).

### Step 3 — Report and log

- To the user: **GATE PASS/FAIL**, round count, cumulative accepted/rejected,
  the applied-fix list, the rejected policy/impl-micro list (transparency),
  and unresolved items on FAIL.
- Append per-round history to the `--log` location: date · target · findings /
  accepted / rejected / dup / verdict per round · final result · tags
  (`[primary-only]` / `[dual]` / `[pass-with-notes]`).
- If a pre-validation script exists (Step 0.2), optionally re-run it after the
  gate to confirm auto-fixes didn't break formatting rules.
- **Final approval is the user's.** Auto-fixes were applied, so remind them:
  "restore points at `<file>.pre-gate-*` can roll everything back." Never
  commit, push, or apply to production.

## Reviewer prompt template — primary (fresh Agent subagent)

> Step 0.5 instantiates the placeholders (`<…>`) into `REVIEW_PROMPT_PRIMARY`.

> Review the following as a **plan document** — not a spec. Goal: catch only
> the **contract and consistency defects** that block starting implementation.
> **Read-only review: do not create, edit, or delete any file.** Report only;
> the orchestrator applies fixes.
>
> Targets: `<paths>`. (For companion sets, also check cross-document
> consistency.)
> Locked policy (proposals to change these are **out of scope** — report only,
> never adopt): `<collected invariants>`
>
> **Verdict altitude (use exactly this bar):** PASS/FAIL on completeness of
> contracts, decisions, and schemas. **Impl-micro is not a failing reason** —
> poll intervals, timeouts, HTTP codes, exact endpoint/file path strings, copy
> text, hash algorithm choice are "settled at implementation time"; their
> absence is not a defect.
>
> Check: ① **plan-specific review focus (top priority):**
> `<plan-specific review focus>` ② contract/decision completeness — are the
> contracts this plan claims closed, without gaps or contradictions
> (concurrency, state transitions, failure/rollback, idempotency, interface
> boundaries — as fits the domain)? ③ **verify code-fact citations against
> the actual code** (start from the extracted list below; open files, check
> file/line/behavior): `<code fact citations>` ④ unresolved-but-unmarked gaps
> ⑤ cross-document contradictions and terminology drift ⑥ security /
> data-loss blockers.
>
> Report each finding as:
> `title / file(or section) / severity(critical|high|medium) /
> isContractLevel(true|false) / isPolicyChange / isImplMicro / rationale`.
> End with `VERDICT: PASS|FAIL` + one-line reason. No praise, no summaries —
> defects only.
>
> **Zero findings plus `VERDICT: PASS` is a normal, expected outcome.** Do not
> excavate defects to have something to report — when unsure, not reporting is
> correct. `VERDICT: FAIL` only when **real critical/high contract defects
> exist**; if only medium remains, list them but verdict PASS. (If a
> prior-round disposition history is attached, re-reporting anything
> substantially identical to it is forbidden.)

## Reviewer prompt template — codex variant (`codex:codex-rescue` agent)

Delivered as the agent's task via the Agent tool
(`subagent_type: "codex:codex-rescue"`). No CLI fallback — without the agent,
run single-voice (see Step 1). The task text **starts with the routing tokens
`--wait --fresh`** (Step 1.5): the forwarder strips them and runs Codex in the
foreground in a fresh session, so the reply is the findings, not a job id.

- **`--codex-mode adversarial`** prepends one line: "Attack this plan's
  contracts: under which assumptions, orderings, concurrency, or failure paths
  does it break? No goodwill, no summaries."

**Prompt** (same bar as the primary, condensed):

> --wait --fresh [adversarial line if enabled] Read-only review — do not
> create, edit, or delete any file. Review the following as a 'plan document'
> (not a spec). Goal: only the contract/consistency defects that block
> implementation. Do not read skill definition directories (`skills/`,
> `.claude/skills`) — only the target plan and the code it cites.
> Targets: `<paths>` · Locked policy (change proposals are out of scope —
> report only): `<collected invariants>`
> Verdict altitude: PASS/FAIL on contract/decision/schema completeness only.
> Impl-micro (poll/HTTP codes/endpoint paths/file path strings/copy/hash
> choice) is "settled at implementation" = not a failing reason.
> Check: **plan-specific focus (top priority)** `<plan-specific review focus>`
> / contract & decision completeness (domain-appropriate) / code-fact
> citations verified against real files: `<code fact citations>` / unmarked
> unresolved gaps / cross-document contradictions / security & data loss.
> Each finding: `title·file·severity·isContractLevel·isPolicyChange·
> isImplMicro·rationale`. End with `VERDICT: PASS|FAIL` + one line. No praise.
> Zero findings + PASS is a normal outcome — do not excavate. FAIL only on
> real critical/high contract defects; medium-only lists still verdict PASS.
> If prior-round history is attached, do not re-report matches.

## Finding classification

| Finding type | Disposition |
|---|---|
| Contract defect (atomicity · idempotency · enums · interfaces · contradiction · code mismatch · unmarked gap) | **Accept → auto-fix → log** |
| Locked-policy change proposal (redefinition · scope change · decision reversal) | **Reject → log "out of scope (policy)"** (label explicitly if security/feasibility blocker) |
| Impl-micro (poll · HTTP codes · paths · copy · hash choice …) | **Reject → log "out of scope (implementation-time)"** |
| Ambiguous (possibly policy) | **Hold the fix → surface "needs confirmation"** |

## Degradation & safety

- Second voice unavailable → single-voice, same loop (`[primary-only]`), with
  a one-line note that confidence is reduced.
- Second voice replies empty, or without a `VERDICT:` line → `[codex-degraded]`
  for that round (Step 1.4); it never counts as a PASS vote.
- Primary subagent also fails → stop and report to the user (BLOCKED).
- **Never:** edit locked policy · auto-commit/push · apply to production ·
  edit files outside `<plan-path>`. Restore points always remain.
- If rounds stop converging (the same defect unresolved two rounds in a row),
  stop and ask for human judgment (loop breaker).
