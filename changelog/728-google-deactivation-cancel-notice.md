# What's new

## Google account emails with the EMS card layout (welcome, reset, deactivation, cancellation, reactivation):

- Every email about a Google Workspace account, for students and staff, now uses a shared card layout (design by Luis): a badge with the event, a title, a card with the account's data and a coloured note, an "Open my email" button and a common footer. Its colours come from the company's email colours (Settings > General > Emails), so a change of house style needs no code.
- New: when a scheduled deactivation is cancelled (unarchiving the person, or "Cancel scheduled deactivation"), EMS emails them that the account will not be deactivated, to the same personal and corporate addresses that got the warning.
- New: when a suspended account is reactivated, EMS emails the person that it is active again. An unarchive within the grace period sends only the cancellation, never both.
- New: a password reset now sends its own "your password has been reset" email instead of reusing the welcome one, which told people who already had the account that it had just been created.
- The layout is a QWeb view (`ems.mail_layout_card`, wrapped per family by `ems.mail_layout_google`) set on each `mail.template` through `email_layout_xmlid`, so it can be reused for other EMS emails (strikes next). Catalan and Spanish translations included.
