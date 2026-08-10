/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { blockingActionFormView } from "./blocking_action_form";

const IMPORT_LOADING_MESSAGE = _t("Importing the schedule, please wait...");
const CONTINUE_LOADING_MESSAGE = _t("Processing, please wait...");

// Shares the exact same full-window blocking overlay the course transition wizard uses
// (blocking_action_form.js) - both buttons' own server methods can be genuinely slow (leaving
// the intro screen parses the whole XML; the final "Import" click does the real write:
// resource.calendar/ems.teaching/ems.attendance_template), not just the save that precedes them.
//
// Rewritten 2026-08-10 (developer feedback: "durante la importación... debería aparecer el
// loading modal que bloquea toda la ventana, el mismo que usamos durante la migración") - the
// earlier, bespoke version only wrapped 'beforeExecuteActionButton' and unblocked immediately
// after (in a 'finally', before the button's own RPC call even started), on the assumption that
// "the button's own server method runs after the save and is comparatively cheap." That was true
// for "Continue" (the slow parsing happens *during* the save, via '_continue_from_intro'), but
// false for "Import": 'import_planner_data()' IS the slow part, and it runs entirely *after* the
// save - so the overlay was disappearing right as the real, slow write was about to start,
// leaving the window looking unblocked (and, per the original bug report this was meant to fix,
// hung) for the one click that most needed it. 'blockingActionFormView' avoids this by design -
// it only unblocks in 'afterExecuteActionButton', which the framework calls after the ENTIRE
// click (save + the button's own RPC + its resulting action), covering whichever phase turns out
// to be the slow one instead of assuming which.
registry.category("views").add(
    "ems_working_schedules_import_wizard_form",
    blockingActionFormView({
        action_continue: () => CONTINUE_LOADING_MESSAGE,
        import_planner_data: () => IMPORT_LOADING_MESSAGE,
    }),
);
