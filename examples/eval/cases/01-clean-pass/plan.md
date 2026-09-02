# Account Data Export — Implementation Plan

## Goal

Let an account owner request a CSV export of their account data from the
settings page and download it once it is ready. Exports are generated
asynchronously.

## Scope

In: export request, background generation, download, expiry.
Out (v1): scheduled or recurring exports, exports of other users' data,
formats other than CSV.

## Decisions

- One export job per request; a request never blocks the UI.
- Format is CSV (UTF-8, header row). The column set is the account profile,
  addresses, and order headers. Order line items are out of v1.
- Files expire 7 days after they become ready; expired files are deleted.
- No cancel in v1: a running export finishes or fails on its own.

## States

| State | Meaning | Exits |
|---|---|---|
| REQUESTED | Accepted, not started | → RUNNING (a worker picks it up) |
| RUNNING | Worker generating the file | → READY (file complete) · → FAILED (error after the retry budget) |
| READY | File downloadable | → EXPIRED (7 days after READY) |
| FAILED | Terminal for this request; partial file deleted | none. The owner may request again |
| EXPIRED | Terminal; file deleted | none. The owner may request again |

Every state above is reachable and every non-terminal state has a defined
exit. A request is identified by an opaque id; every state change is
recorded with a timestamp.

## Concurrency and idempotency

- At most one export per account may be in REQUESTED or RUNNING. The check
  and the creation happen atomically at request time; a second request that
  arrives while one is active receives the existing request's id instead of
  creating a new one.
- Worker retries: a RUNNING export that fails transiently is retried up to
  the retry budget. Each attempt regenerates the file from scratch and
  replaces any partial output, so retries are idempotent.
- READY files are immutable. A new request after READY creates a new export
  rather than replacing the old file.

## Data contract

- Input: the account id from the session, nothing else.
- Output: one CSV file, header row first, one row per record, RFC 4180
  quoting, timestamps in ISO 8601 UTC.
- Rows include only records owned by the requesting account. Deleted
  records are not included.

## Access

- Download requires the owner's authenticated session and the request id.
- Download links are signed and expire with the file. A link for an EXPIRED
  or FAILED export returns an error, never a stale file.

## Failure and rollback

- A FAILED export leaves no file behind: the partial output is deleted
  before the state flips to FAILED.
- Expiry deletion is idempotent; running it twice on the same export is a
  no-op.
- Worker crash mid-run: the export stays RUNNING until a lease timeout,
  then is re-queued as a retry under the same request id.

## Security and privacy

- The CSV contains personal data. It is stored encrypted at rest and served
  only through authenticated, signed downloads.
- Export requests and downloads are written to the audit log (who, when,
  which request id).

## Settled at implementation time (not part of this plan)

Polling versus push for status updates, exact endpoint paths and HTTP
status codes, the signed-URL TTL within the 7-day window, retry budget and
lease timeout values, storage bucket layout, file naming.

## Open questions

None open. Line-item export is scheduled for v2 and is out of scope here.
