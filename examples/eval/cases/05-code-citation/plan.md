# Invoice Discounts — Implementation Plan

## Goal

Apply coupon discounts to invoices at issue time, with totals that
reconcile to the ledger to the cent.

## Decisions

- A coupon applies to the invoice subtotal, before tax.
- At most one coupon per invoice in v1.
- Discount percentages are capped. The cap is the existing
  `MAX_DISCOUNT_PERCENT` constant in `src/billing/invoice.py`, which is 30.

## Calculation contract

The discounted subtotal is computed by the existing `apply_discount()` in
`src/billing/invoice.py`. It rounds **half-up** to the cent, and ledger
reconciliation relies on that: the ledger posts the same half-up rounded
amount, so invoice and ledger agree to the cent for every invoice.

Tax is computed on the discounted subtotal.

## Validation

Coupons are validated by `validate_coupon()` in `src/billing/coupons.py`
(expiry, usage limit, eligible plan) before the discount is applied. An
invalid coupon fails the invoice issue with a validation error; nothing is
written.

## Idempotency

Issuing an invoice is idempotent on the invoice id: re-issuing an already
issued invoice returns the existing totals and does not re-apply the coupon
or consume another use.

## States

| State | Exits |
|---|---|
| DRAFT | → ISSUED (totals fixed, coupon use consumed) |
| ISSUED | → PAID · → VOID |
| PAID | terminal |
| VOID | terminal; a VOID invoice releases the coupon use |

## Settled at implementation time

Error codes, coupon input UI, ledger posting format.
