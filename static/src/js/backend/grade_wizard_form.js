/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { blockingActionFormView, overlayLines } from "./blocking_action_form";

/**
 * Blocking overlays for the three grade wizards. Creating the sessions of a whole round
 * (232 sessions and ~24.000 grade lines at this centre) and importing one Esfer@ file
 * (minutes, several thousand rows) both look frozen behind Odoo's small "Loading" pill.
 *
 * The messages deliberately name the scope the operator has just chosen rather than a
 * percentage — see blocking_action_form.js for why there is no live counter.
 */
registry.category("views").add(
    "ems_grade_session_wizard_form",
    blockingActionFormView({
        action_create_sessions: () => overlayLines(
            _t("Creating the evaluation sessions…"),
            "",
            _t("One session per group and subject of the selected scope, each one filled "
               + "with its students and their outcome lines."),
            _t("This can take several minutes — do not close this window."),
        ),
    }),
);

registry.category("views").add(
    "ems_grade_session_state_wizard_form",
    blockingActionFormView({
        action_apply_state: () => overlayLines(
            _t("Changing the state of the evaluation sessions…"),
            "",
            _t("This can take a while — do not close this window."),
        ),
    }),
);

registry.category("views").add(
    "ems_grade_import_wizard_form",
    blockingActionFormView({
        action_import: () => overlayLines(
            _t("Importing the grades…"),
            "",
            _t("Every row of the file is matched against the student's enrollment and "
               + "written into its evaluation session."),
            _t("A file can take several minutes — do not close this window."),
        ),
    }),
);
