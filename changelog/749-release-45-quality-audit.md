# Internal changes

## Quality audit of v18.0.0.45.0 (duplication between the branches integrated together):

- The centre language (`res.company.ems_lang`) is read one way: `res.company._ems_centre_env()` or the field itself. Removed `ems.minute._ems_centre_lang()`/`_ems_centre_env()` and `ems.convalidation._ems_resolution_lang()`; `scope_code`, the agreement follow-ups, the student card check page and the public group schedules use the same helper.
- One `ir.actions.report` override (`models/shared/ir_actions_report.py`) prints the centre's documents in the centre language, listed once in `CENTRE_LANG_REPORTS`: the minute, the student card and the convalidation resolution. It replaces the two overrides of the minute and the student card, so every report render goes through one check instead of two. The public group schedule stays out: its Print menu entry follows each user's language.
- Snooze: the server is the only source of the 1/3/7 choices and of the "later of today and the due date, plus the days" rule; the web client asks `mail.activity.ems_snooze_choices()` instead of repeating both. The snooze and the daily summary read "today" from the same clock (`ems.datetime_utils.utc_to_local_date(fields.Datetime.now())`).
- Student card level colours: the palette (key, label, colour) is declared once and the field's selection is built from it.
- Tests: the student card and the minute PDF are checked in a non-Catalan centre language; the snooze choices are tested; the minute tests set the centre language instead of patching a method (which left the codes in Catalan while the rest of the minute was in English).
- Measured on this box's data: the snooze popover adds one call of ~7 ms cold (0.02 ms warm); the centre-language helper costs ~0.005 ms warm.
