# Search Ranking v2 — Rollout Plan

## Goal

Replace the current search ranking with ranking v2 for all users, in
stages, behind a feature flag, with a kill switch.

## Decisions

- One boolean flag `search_ranking_v2`, evaluated per request.
- Rollout by cohorts: internal → 1% → 10% → 50% → 100%. Each stage runs for
  at least 3 days before the next.
- Kill switch: setting the flag to off returns every user to v1 on their
  next request. No data migration is involved in either direction.
- The two rankings share the index; v2 changes scoring only.

## Cohort assignment

A user is assigned to a bucket by a stable hash of the user id, so the same
user sees the same ranking across sessions and devices. Anonymous sessions
are bucketed by session id and may therefore flip between sessions; this is
accepted for v1 of the rollout.

## Stage gates

A stage advances only when, for the bucket on v2 versus the bucket on v1:

- click-through on the first page is not worse,
- the zero-result rate is not worse,
- p95 latency is within budget.

The exact thresholds are owned by product and are recorded in the rollout
ticket before each stage; they are intentionally not fixed in this
document.

## Rollback

Flipping the flag off is the rollback. It is safe at any stage because v2
writes nothing: it reads the shared index and changes scoring only. There
is no state to unwind.

## Monitoring

Dashboards split every search metric by ranking version. Alerts on the
kill-switch metrics page the search on-call.

## Settled at implementation time

Flag storage, hash function, dashboard layout, alert thresholds.

## Glossary

- Cohort: the set of users currently assigned to a rollout stage.
