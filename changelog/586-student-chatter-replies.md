# Changes

## A conversation on a contact's chatter stays between whoever writes and the contact:
- Creating a contact no longer makes its creator follow it. Until now whoever registered students and families received by email every message later written on their chatter (issue #586).
- The administrator account is removed as a follower of every contact (migration): it followed the ones it had created, so those messages also reached the EMS mailbox.
- Writing a message on a contact still makes you follow it, which is how you get the answers.

# Internal changes

## Answers by email filed on the chatter (prepared, needs production configuration):
- Verified with a test that an answer sent by email to a chatter message is filed on the contact's chatter, as written by the family, and notified to the teacher who wrote. It only works once production has an incoming mail server reading an answers mailbox, and that mailbox's address is different from the bounce address: with both set to `ems`, as now, Odoo discards every answer as a bounce. Steps in `docs/en/developers/shared/chatter_email_answers.md`.
- A development machine never reads a mailbox: `fetchmail.server.fetch_mail()` does nothing there and `devel.sh` switches the restored incoming mail servers off, so a restored copy cannot take the answers away from production.

# Related with

- Closes #586
