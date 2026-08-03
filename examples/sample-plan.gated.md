# Payment Refund Feature — Implementation Plan

> **This is the post-gate version** of [`sample-plan.md`](sample-plan.md),
> produced by a real 3-round plan-preflight run (dual-voice, GATE PASS
> [pass-with-notes]). Every addition below was an auto-applied contract fix —
> compare with the original to see exactly what the gate does.
> Round-by-round history: [`sample-plan.review.md`](sample-plan.review.md)

## Goal

Let customers request a refund for a completed order from the order-detail
page. Support and finance both approve before money moves.

## Decisions (locked)

- Refunds are **manual-approval only** — no auto-refund path, regardless of
  order amount. (Business decision, finance sign-off 2026-07.)
- Refund window: 30 days after delivery confirmation.
- Payment provider stays **PayGate** — no provider change in this project.

## Flow

1. Customer taps "Request refund" → state `REQUESTED`
   - Eligibility is checked **at creation**: within 30 days of the order's
     delivery-confirmation timestamp. Out-of-window requests are refused.
   - Invariant: **at most one active refund per order** (active = any state
     other than `REJECTED`, `REFUNDED`, `ABORTED`). Additionally, an order
     whose refund reached `REFUNDED` accepts **no further refund requests** —
     v1 is full-amount-only, so a completed refund exhausts the order.
     Duplicate or concurrent creates are refused.
2. Support reviews → `APPROVED_L1` or `REJECTED`
3. Finance reviews → `APPROVED_FINAL` or `REJECTED`
   - The 30-day window is re-checked at final approval (long-pending requests).
4. On the `APPROVED_FINAL` transition, the **system** (single owner: the state
   machine — not a human action; mechanism settled at implementation) initiates
   the provider call → `PROCESSING`
5. Provider result: confirmed → `REFUNDED` · failed/ambiguous → `PAYMENT_FAILED`
   - `PAYMENT_FAILED` is operator-resolved (finance role; the refund is
     already dual-approved, so the same-principal rule does not apply here):
     retry (→ `PROCESSING`), confirm an out-of-band settlement (→ `REFUNDED`,
     provider reference recorded), or abort with reason (→ `ABORTED`,
     terminal). It is never silently retried and never terminal without an
     operator decision.

Rejection semantics: `REJECTED` is terminal **for that request**. The customer
may submit a new request while still inside the 30-day window; the
one-active-refund invariant applies to the new request.

## Interfaces

- `POST /api/refunds` — create request `{orderId, reason}` (enforces: the
  requesting principal owns the order · window check · one-active-refund
  invariant, see Flow)
- `PATCH /api/refunds/:id` — state transition `{action: approve|reject}`
  - **Authorization contract:** transitions are role-bound — `APPROVED_L1`
    requires the support role, `APPROVED_FINAL` requires the finance role,
    and **the same principal cannot perform both approvals for one refund**.
    Customers cannot invoke approval transitions.
- Provider call: PayGate `cancelPayment(tid, amount)` — `tid` is the order's
  original payment transaction reference (owned by the payments domain,
  read-only here); `amount` is the order's full paid amount (v1 is
  full-amount-only)
  - **Idempotency contract:** the call carries an idempotency reference
    (the refund `id`); the provider transaction reference and outcome are
    recorded before the state transition completes. On timeout or ambiguous
    result, **query the provider for the actual outcome before any retry** —
    a money-moving call is never blind-retried.

## Data

`refunds` table: `id, order_id, state, reason, requested_at, resolved_at,
provider_ref, provider_result, approved_l1_by, approved_final_by,
abort_reason, failure_resolved_by`

- `state` ∈ {REQUESTED, APPROVED_L1, APPROVED_FINAL, PROCESSING,
  PAYMENT_FAILED, REFUNDED, REJECTED, ABORTED}
- Uniqueness: at most one **active** refund per `order_id` (see Flow invariant)
- Window checks read the order's delivery-confirmation timestamp (owned by the
  orders domain; read-only here)

## Open questions

- Partial refunds: out of scope for v1 (full amount only) — confirmed.

