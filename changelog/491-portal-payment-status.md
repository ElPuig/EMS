# What's new

## Enrollment payment status in the student portal:
- The **Payment** block of a confirmed enrollment now lists one row per installment with its own
  due date, amount and status (**Paid** / **Pending**), read from the enrollment invoice instead
  of from the payment plan alone. A two-installment plan correctly shows the July one as paid
  while the September one is still pending, which the invoice's overall state (`partial`) could
  not express. With no invoice issued yet, the page falls back to the plan's own breakdown
  exactly as before.
- The schedule does not depend on the enrollment carrying a payment plan. An enrollment confirmed
  from the back office has neither a payment plan nor a payment method (only the portal
  confirmation writes those), and used to show "payment information not yet specified" even when
  its invoice was issued and fully paid. Those enrollments now show their schedule like any other,
  and the placeholder is only shown when there really is nothing to report.
- Registering the payment of an installment now posts a notice on the enrollment itself, so the
  family sees it both in the **Communications** block of the enrollment page and in the portal's
  **Communications** menu. The notice names the installment, the amount and the due date, and is
  written in the family's own language rather than in the language of whoever registered the
  payment.
- The notice is portal-only and deliberately sends no email: it carries its own message subtype
  (`ems.mt_enrollment_payment`) that no follower is subscribed to, so making a payment visible
  never turns into a mailing to everybody following the enrollment.

# Internal changes

## Payment status plumbing and its coverage:
- `sale.order._ems_portal_installments()` hands the portal plain values (number, label, due date,
  amount, residual, paid) read under `sudo()`, so no portal page ever needs access to
  `account.move`. `_ems_portal_message_domain()` moves the enrollment page's own message filter
  into the model, where the tests assert on exactly what the page renders.
- The notification hangs off Odoo's own reconciliation hooks: the pre-hook snapshots which
  installments were open, the post-hook announces those that became fully reconciled. An
  installation upgrading with years of already-paid invoices therefore announces nothing
  retroactively, with no stored flag and no backfill migration.
- Installment labels are built server-side rather than assembled from QWeb text nodes, which were
  being exported as untranslatable word fragments ("Payment", "of", "(due").
- New `TestPortalPaymentStatus` covers single and deferred plans, partial payments, the
  once-per-installment rule, the absence of email, non-enrollment invoices and the family's
  language; two browser tours cover the rendered badges and the notice on both portal pages.
- Family and secretary manuals updated in the three languages, with screenshots of the payment
  schedule as the family sees it (pending installments and a collected one), plus the developer
  documentation and the Catalan/Spanish translations.
