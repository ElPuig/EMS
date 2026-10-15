/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { blockingActionFormView, overlayLines } from "./blocking_action_form";

/**
 * Blocking overlay for the title import (issue #635): registering the titles of a whole level
 * makes every student without a group leave the centre (portal, Google, archive), which takes
 * a while. See blocking_action_form.js for why there is no live counter.
 */
registry.category("views").add(
    "ems_title_import_wizard_form",
    blockingActionFormView({
        action_preview: () => overlayLines(
            _t("Reading the file…"),
            "",
            _t("Every student of the file is looked up in EMS with their academic record."),
        ),
        action_apply: () => overlayLines(
            _t("Registering the titles…"),
            "",
            _t("The students with no group leave the centre as graduates."),
            _t("A file can take several minutes — do not close this window."),
        ),
    }),
);
