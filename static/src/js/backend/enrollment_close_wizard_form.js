/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { blockingActionFormView, overlayLines } from "./blocking_action_form";

/**
 * Blocking overlay for closing unconfirmed enrollments (issue #643): every withdrawal or exit
 * revokes portals and warns Google accounts, which takes a while for a whole course.
 * See blocking_action_form.js for why there is no live counter.
 */
registry.category("views").add(
    "ems_enrollment_close_wizard_form",
    blockingActionFormView({
        action_apply: () => overlayLines(
            _t("Closing the unconfirmed enrollments…"),
            "",
            _t("Each person gets the action shown in the preview."),
            _t("It can take several minutes — do not close this window."),
        ),
    }),
);
