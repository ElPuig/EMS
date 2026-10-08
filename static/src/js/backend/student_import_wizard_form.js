/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { blockingActionFormView, overlayLines } from "./blocking_action_form";

/**
 * Blocking overlay for the Esfera student import: a class of 120 students with their
 * families takes ~20 seconds, and a whole level several minutes, behind Odoo's small
 * "Loading" pill. See blocking_action_form.js for why there is no live counter.
 */
registry.category("views").add(
    "ems_student_import_wizard_form",
    blockingActionFormView({
        action_import: () => overlayLines(
            _t("Importing the students…"),
            "",
            _t("Every row of the file creates or updates the student and their family contacts."),
            _t("A file can take several minutes — do not close this window."),
        ),
    }),
);
