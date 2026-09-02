# Partner Order Webhooks — Ingestion Plan

## Goal

Receive order events pushed by partner systems, validate them, and apply
them to our order records so that partner-side changes show up in our
system within minutes.

## Decisions

- Partners push events to us; we never poll partner APIs.
- We acknowledge an event with a 2xx only after it is durably persisted.
  Anything else is a non-2xx and the partner retries.
- One endpoint per partner; each partner has its own signing secret.

## Event contract

```json
{
  "event_id": "string, partner-assigned",
  "event_type": "order.created | order.cancelled",
  "order_ref": "string, partner order reference",
  "occurred_at": "ISO 8601",
  "payload": { "...": "type-specific" }
}
```

Signature: an HMAC over the raw body using the partner's secret, carried in
a request header. Events with a bad signature are rejected with a non-2xx
and not stored.

## Processing

Each accepted event moves through these states:

| State | Meaning | Exits |
|---|---|---|
| RECEIVED | Persisted raw, acknowledged to the partner | → VALIDATED · → REJECTED |
| VALIDATED | Schema and reference checks passed | → APPLIED |
| APPLIED | Change written to the order record | terminal |
| REJECTED | Failed validation; kept for inspection | terminal |

Handling by type:

- `order.created`: create the order record if the reference is unknown.
- `order.updated`: merge the changed fields into the existing order.
- `order.cancelled`: mark the order cancelled and release any reservation.

Events are applied in arrival order, one worker per partner.

## Retries

Partners retry on any non-2xx, with backoff, for up to 24 hours. Our worker
retries a failed apply step up to three times before the event is parked
for manual review.

## Alerting

- Signature failures above a threshold per partner page the on-call.
- Events sitting in QUARANTINED for more than one hour raise a ticket.

## Risks

- Partners have told us events may arrive out of order under load.
- Partner clock skew makes `occurred_at` unreliable for ordering.

## Settled at implementation time

Header names, the exact backoff schedule, threshold values, endpoint paths,
queue technology.
