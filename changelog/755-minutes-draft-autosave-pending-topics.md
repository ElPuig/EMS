# What's new

## Draft of the minute for the participants:
- Sending a minute for approval opens a dialog that offers, ticked, to also send its draft to everybody convened, whether they came or not: the staff get an email with a link to the draft's PDF (always as the minute stands), and the guests from outside EMS get the PDF attached in a message of their own. They review it while the meeting is fresh and reply with corrections before it is approved.
- While the meeting is held or the minute waits for approval, Actions → "Send the draft to the participants" sends it again; the minute's history records how many people got it.

# Fixes

## Writing a minute no longer loses the cursor when it saves by itself:
- The autosave redrew the form and took the focus out of the text box being written in, so whoever kept typing wrote somewhere else. It now saves without redrawing when only existing lines changed, and when it adds new lines it puts the cursor back where it was.

## Pending topics no longer pile up repeated from meeting to meeting:
- A minute created from the form carried the previous minute's pending topics twice (the carried-over fields were readonly and never reached the server), and each following minute doubled them again. Each topic is now carried once, also from a minute that already holds repetitions; the upgrade removes the repetitions from the minutes not approved yet.

# Internal changes

## Minutes (issue #755):
- New transient model `ems.minute.submit.wizard` (access for teacher, secretary and academic admin: whoever can write minutes); `ems.minute.action_open_submit_dialog`/`action_send_draft`; the call and the draft share `_ems_meeting_mail` (QWeb `ems.minute_call_email` / new `ems.minute_draft_email`).
- `minute_form.js` autosave: `reload: false` unless the changes create one2many lines; otherwise the caret is remembered and restored after the redraw. Regression tour `ems_minute_autosave_keeps_focus`.
- `force_save` on `previous_minute_id`, `followed_agreement_ids` and `carried_from_minute_id`; `_ems_preload_previous` carries each topic once. Migration `18.0.0.46.0/post-migrate.py` deletes repeated pending topics of non-approved minutes.
