# Changes:

## Emails sent from a development machine say so in their subject:
- Every email that leaves a development machine (the ones the dev mail guard lets through: the
  developer's redirect inbox and the allowlisted addresses) now has its subject prefixed with
  `[DEV]`, so it can be told apart from production's own in an inbox that receives both.
  Production and CI are unaffected.
