# Account Deletion — Implementation Plan

## Goal

Let a user delete their account from settings. Personal data is removed;
records we are legally required to keep are retained in pseudonymised form.

## Decisions (locked)

These were settled with legal and product and are not up for review here:

- Personal data is hard-deleted. There is no soft-delete flag and no
  "deactivated" account that support can silently restore.
- Deletion executes 14 days after the user confirms (cool-off). There is no
  immediate-deletion option, not even for support.
- Financial records (invoices, payments) are retained for 5 years under tax
  law, with the customer identity replaced by a pseudonymous key.
- One region; no cross-region replication concerns in v1.

## Flow

1. The user requests deletion in settings and re-authenticates.
2. We send a confirmation email; the request is confirmed when the link is
   used.
3. The account is frozen for the cool-off period.
4. On the scheduled date the deletion job runs.

## States

| State | Meaning | Exits |
|---|---|---|
| REQUESTED | Deletion asked for, not yet confirmed | → CONFIRMED (email link used) · dropped after 48h without confirmation |
| CONFIRMED | Cool-off running, account frozen | → SCHEDULED (job enqueued for the execution date) |
| SCHEDULED | Waiting for the execution date | → EXECUTED |
| EXECUTED | Personal data removed, financial records pseudonymised | terminal |

## Frozen account

During the cool-off the user can still sign in but sees only a banner with
the scheduled date and a **cancel deletion** button. All other actions are
blocked. Support sees the same banner and cannot change the date.

## Deletion job

- Deletes profile, addresses, preferences, sessions, API tokens, uploaded
  files, and support conversations.
- Financial records are deleted together with the profile so that no
  customer identity remains anywhere.
- The job is idempotent: re-running it on an EXECUTED account is a no-op.
- Partial failure leaves the account in SCHEDULED with the failure
  recorded; the job is retried on the next run until it completes.

## Notifications

Confirmation email at request time; a reminder 2 days before execution; a
final email on execution to the address on file, sent before the address
is deleted.

## Settled at implementation time

Email copy, the exact job schedule, batch sizes, storage-level deletion
mechanics, audit log format.
