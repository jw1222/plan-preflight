# plan-preflight

[한국어](README.md) | **English**

**Preflight checks for your implementation plans.**

A [Claude Code](https://claude.com/claude-code) skill that drives a plan
document to a binary **PASS / FAIL** verdict before you write a single line of
code. Two AI reviewers examine the plan independently, contract-level defects
get fixed automatically, and the loop re-reviews until the gate closes —
typically in 1–3 rounds.

```
/plan-preflight docs/payment-refund-plan.md
```

```
[PROGRESS] R1: accepted 2 (crit/high 1 · med 1) · rejected 3 · dup 0 · verdict continue
[PROGRESS] R2: accepted 0 · rejected 1 · dup 2 · verdict PASS

GATE PASS (2 rounds)
  fixed   : refund idempotency contract added · rollback step ordering closed
  rejected: 3 impl-micro (retry interval, endpoint path, error copy) · 1 policy proposal
  restore : docs/payment-refund-plan.md.pre-gate-20260803T101500Z
```

## Why

AI makes writing plans cheap. It did not make *trusting* them cheap. Teams
generate a plan in minutes, then either ship on vibes or burn an afternoon in
review threads. plan-preflight treats the plan like CI treats code: a gate with a
binary verdict.

Building a reliable gate is harder than it looks. Two failure modes kill the
naive "hey Claude, review my plan in a loop" approach — plan-preflight was built
around both (each discovered the hard way, in production use):

**1. The bar slips.** Ask a strong reviewer to review a *plan* and by round
three it demands poll intervals, HTTP status codes, and exact endpoint paths.
A plan legitimately defers those — so PASS becomes unreachable, forever one
"missing detail" away. plan-preflight pins the review altitude in every prompt:
**contracts, decisions, and schemas are judged; implementation micro-detail
is explicitly not a defect.**

**2. Reviewers hate reporting empty-handed.** A cold reviewer told to "find
defects" will manufacture medium-severity findings rather than return nothing.
Rounds balloon. plan-preflight tells reviewers that **zero findings is a normal
outcome**, gates rounds on **critical/high severity only**, and attaches each
round's disposition history so handled findings can't be re-reported.

## What it does

| Element | Behavior |
|---|---|
| Verdict target | "Is this plan ready to implement?" — nothing more |
| Dual review | Claude + optional codex second voice (auto-degrades to single-reviewer) |
| Policy invariants | Locked decisions are collected up front and never modified — change proposals are reported, not applied |
| Auto-fix scope | Contract-level defects only: missing idempotency/rollback/state contracts, cross-document contradictions, citations that don't match the code, unmarked open questions |
| Termination | PASS when a round yields zero critical/high findings (medium-only = immediate pass-with-notes) · FAIL after the round cap with the unresolved list |

## What it never does

- Change a locked decision, even if a reviewer argues for it
- Edit any file other than the plan itself
- Commit, push, or deploy
- Edit without leaving a restore point (`<file>.pre-gate-<timestamp>`)

## Install

```bash
git clone https://github.com/jw1222/plan-preflight
cp -r plan-preflight/skills/plan-preflight ~/.claude/skills/
```

That's the whole install. One markdown file, no dependencies, no build step.

**Optional second reviewer:** dual-voice mode activates only when all three
are true:

1. the **openai-codex Claude Code plugin** is installed (it provides the
   `codex:codex-rescue` agent),
2. the **OpenAI Codex CLI** is installed, and
3. you are **logged in** to it (`codex login`, or an `OPENAI_API_KEY` in the
   environment).

If any of these is missing — including "plugin installed but not logged in" —
the agent call fails and plan-preflight continues single-voice (`[primary-only]`
from the start, or `[codex-degraded]` for the affected round). Nothing breaks.

## Usage

```bash
# Basic — gate one plan
/plan-preflight docs/checkout-refactor-plan.md

# Companion documents (cross-document consistency is checked too)
/plan-preflight plans/migration-v2.md,plans/migration-brief.md

# High-risk plan: adversarial second voice
/plan-preflight docs/billing-plan.md --codex-mode adversarial

# Explicit invariants file, extended rounds
/plan-preflight plan.md --invariants decisions.md --base 3 --max 5
```

| Option | Default | Meaning |
|---|---|---|
| `--invariants <file>` | auto-collected | Source of locked policy |
| `--codex on\|off\|auto` | `auto` | Second reviewer toggle |
| `--codex-mode rescue\|adversarial` | `rescue` | Second-voice depth |
| `--base N` / `--max M` | 3 / 5 | Round budget / extended cap |
| `--log <file>` | `<plan>.review.md` | Round history location |

Works on `.md`, `.html`, `.txt` — any plan the reviewers can read.

**Output language:** default is English. Want the report and log in Korean —
or anything else — instead? Just ask for it in the invocation:

```
/plan-preflight docs/plan.md — 답변은 한글로 해줘
/plan-preflight docs/plan.md, please reply in Korean
```

Everything sent to a reviewer stays in English — not just the round-1 prompts
but round 2+ dispatches, prior-round disposition blocks, and nudges. The
prompts were tuned in English, and non-English input makes CLI-backed
reviewers (Codex) drift into third-language reasoning (observed: Korean
prompts → Japanese chain-of-thought). Only the report shown to you and the
`--log` file follow your requested language.

## How it works

```
Step 0  Lock target · collect invariants · extract code citations
        · derive plan-specific focus · assemble both prompts (once)
Step 1  Resolve second reviewer (agent present? dual : single)
Step 2  ROUND LOOP (sequential rounds, parallel voices within a round)
          dispatch both reviewers → classify findings
          → reject policy/impl-micro → auto-fix contract defects
          → severity gate: no crit/high? PASS : next round
Step 3  Report PASS/FAIL · applied fixes · rejected list · restore points
```

Full mechanics are in [`skills/plan-preflight/SKILL.md`](skills/plan-preflight/SKILL.md)
— it is the skill, and it is the documentation.

## See a real run (no tokens required)

The `examples/` directory contains a complete gate run you can read instead
of executing:

| File | What it is |
|---|---|
| [`sample-plan.md`](examples/sample-plan.md) | A refund-feature plan with deliberate contract gaps (annotated answer key at the bottom) |
| [`sample-plan.gated.md`](examples/sample-plan.gated.md) | The same plan **after** a real 3-round dual-voice run — every addition is an auto-applied contract fix |
| [`sample-plan.review.md`](examples/sample-plan.review.md) | The round-by-round log: findings, severities, the orchestrator's severity override, and the final `GATE PASS [pass-with-notes]` |

Highlights from that run: all 3 planted defects caught in round 1 by both
voices, 4 additional genuine defects found beyond the answer key, zero
locked-policy modifications, zero impl-micro drilling — and in round 3 the
severity gate cut off a reviewer that kept escalating new findings each
round, which is exactly the failure mode it exists for.

## FAQ

**Do I need codex?** No. Single-voice mode runs the identical loop. The
second voice raises confidence; its absence is tagged in the report. If you
*expected* dual-voice but the report says `[primary-only]` or
`[codex-degraded]`, the usual cause is the Codex CLI not being logged in —
run `codex login` and try again.

**Will it "improve" my architecture?** Deliberately not. Decisions you've
locked are out of scope by design. The gate closes *your* plan — it doesn't
substitute its taste for yours.

**Why does it refuse to check poll intervals / endpoint paths?** Because a
plan that specified those wouldn't be a plan — it would be the implementation.
That altitude discipline is the reason PASS is reachable at all.

**Can it review code / PRs?** No, and it will say so. Pre-implementation
plan and design documents only. Use a code review tool after you build.

**Invoke by name or trust auto-triggering?** Explicit invocation
(`/plan-preflight <file>`) is the reliable path and the recommended habit.
Model-initiated triggering works but varies by context.

## License

MIT — see [LICENSE](LICENSE).
