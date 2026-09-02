# Subscription Pause — Implementation Plan

Companion: [brief.md](brief.md) (locked product decisions).

## Goal

Let subscribers pause their subscription from account settings and resume
automatically when the pause ends.

## Pause request

- The subscriber picks a pause length of up to 6 months.
- The pause starts at the end of the current billing period, never
  mid-period, so no proration is needed.
- One pause per billing year, enforced at request time.

## During the pause

- No invoices are generated.
- Access to content is fully blocked; the subscriber sees a "paused" page
  with a resume button.
- The subscriber can resume early at any time; billing restarts at the next
  anchor date.

## Resume

- Automatic on the pause end date, or early on request.
- Billing resumes on the preserved anchor day-of-month.

## States

| State | Exits |
|---|---|
| ACTIVE | → PAUSE_SCHEDULED (request accepted) |
| PAUSE_SCHEDULED | → PAUSED (period end) · → ACTIVE (request withdrawn before period end) |
| PAUSED | → ACTIVE (end date or early resume) |

## Provider

Pauses are implemented on our side: we stop generating invoices. BillCo is
not told about the pause and the provider-side subscription is unchanged.

## Idempotency

Pause and resume requests are idempotent on the subscription id and the
target state; repeating a request already applied returns the current
state.

## Settled at implementation time

UI copy, the exact cron for state transitions, notification schedule.
