# What's new:

## Manual "Mark as identified" action for pending teachers:
- New header button on the employee form, `action_mark_as_identified()` (`models/employees/employee.py`), visible only while `pending_identification` is `True`. Clears `schedule_import_code` (with a chatter note naming the original code) without touching Google Workspace/EMS user creation at all - a standalone, one-way escape hatch (not a bidirectional toggle, since the original placeholder code is gone once cleared) for a pending teacher that will never get an account created from this specific record (e.g. duplicate/unmerged employee, or a post that turns out not to need one).
- Behind a `confirm=` dialog (native Odoo confirmation pattern, same as other one-way actions in this codebase) since it can't be undone.
- Covers issue #378: previously the only way to clear "pending identification" was as a side effect of `action_create_google_account()`, with no manual alternative.

# Fixes:

## Pending teacher stuck after adopting an existing Google account:
- `action_create_google_account()`'s "adopt" branch (employee already has a corporate `work_email`) delegates to `action_create_ems_user()` and returns immediately - it used to skip the `schedule_import_code`-clearing logic entirely, since that logic only lived at the very end of the full-creation success path. A pending teacher resolved via the adopt path (corporate account pre-existing/migrated, not freshly created) stayed stuck showing "Pending identification" forever even after getting a working EMS login.
- Fixed by moving the clearing logic into `_ems_create_user()` (`_gw_clear_pending_identification()`), the single method both `action_create_google_account()` and `action_create_ems_user()` converge on - both paths now correctly confirm identity once a real EMS user is linked, regardless of which one created/adopted the account.
- Confirmed against this box's own dev database: at least one existing pending-teacher record already had a corporate `work_email` set but no linked user - exactly the scenario this fix addresses.

## Pending (and other no-photo) teachers kept showing their old initial after a rename:
- Native Odoo's own `hr.employee.create()` bakes a real SVG placeholder (the initial letter) directly into `image_1920` for any new employee created without a photo - not the live, always-current avatar computation the rest of the app relies on. Every pending-identification teacher hits this 100% of the time, since they're always created with a placeholder name and always renamed later once identified - "Pending teacher (X1)" renamed to the real teacher's name kept showing the old placeholder's initial (e.g. still "P") instead of updating.
- Fixed with a new `hr.employee._refresh_stale_avatar_placeholder()`, called from `write()` whenever the name changes: detects a self-generated SVG placeholder (never a real uploaded photo, which can't be SVG) and regenerates it from the new name. Also fixes the same staleness for an employee with "Disable profile picture" enabled who gets renamed afterward.

## Pending teacher's avatar jumped out of position on the form:
- The employee form's title/avatar row uses a flex layout with only two real items (title, avatar); a pending teacher's own `schedule_import_code` field (only visible while pending) was inserted directly inside that same row, between them - a genuine third item competing for width, which pushed the avatar onto its own line below the buttons instead of its normal top-right slot, only while pending (the field has no layout footprint at all once resolved). Fixed by removing that field from the view entirely (see below - it turned out not to be needed at all), and, for the same underlying reason though not independently reproducible, moving the "Pending identification" ribbon widget to render outside that row too, matching how the native "Archived" ribbon is already positioned.

## Raw schedule-import code no longer shown on the employee form:
- `schedule_import_code` (the raw placeholder like "X1", or the not-yet-confirmed e-mail) was shown read-only on a pending teacher's form, but added nothing a user needs: the same value is already visible in the record's own name until renamed ("Pending teacher (X1)"), and stays on the record afterward via the chatter note posted when it's resolved (manually or through Google account creation). Removed the field from the view; still used internally for import-time matching.
