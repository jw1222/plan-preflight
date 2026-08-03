# Payment Refund Feature — Implementation Plan

> Example plan for trying plan-preflight:
> `/plan-preflight examples/sample-plan.md`
> It contains deliberate contract gaps for the gate to find (and one locked
> decision the gate must refuse to touch).

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
2. Support reviews → `APPROVED_L1` or `REJECTED`
3. Finance reviews → `APPROVED_FINAL` or `REJECTED`
4. Provider refund API call → `REFUNDED`

## Interfaces

- `POST /api/refunds` — create request `{orderId, reason}`
- `PATCH /api/refunds/:id` — state transition `{action: approve|reject}`
- Provider call: PayGate `cancelPayment(tid, amount)`

## Data

`refunds` table: `id, order_id, state, reason, requested_at, resolved_at`

## Open questions

- Partial refunds: out of scope for v1 (full amount only) — confirmed.

<!--
Deliberate gaps a good gate run should surface (do not fix by hand):
  · No idempotency contract on the provider call — a retry after timeout can
    double-refund. (contract defect → should be caught and fixed)
  · REJECTED → re-request allowed or not? State machine doesn't say.
    (unmarked gap → should be caught)
  · What happens when cancelPayment fails after APPROVED_FINAL — no
    failure/compensation path. (contract defect → should be caught)
  · A reviewer may propose "auto-approve small refunds" — that touches a
    locked decision and must be REJECTED as out-of-scope policy.
  · Exact PayGate endpoint URL and retry interval are impl-micro — must NOT
    be demanded by the gate.
-->
