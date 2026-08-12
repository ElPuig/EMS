/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { blockingActionFormView, overlayLines } from "./blocking_action_form";

/**
 * Blocking overlay for the course transition.
 *
 * Applying takes ~24s for a single vocational cycle (127 students) and several minutes for
 * the whole centre. The overlay states what the preview has just promised, which is real
 * information the operator has approved. See blocking_action_form.js for why there is no
 * live progress counter.
 */
function transitionMessage(data) {
    const counts = [
        [data.place_count, _t("join their group")],
        [data.place_later_count, _t("join when their own study transitions")],
        [data.graduate_count, _t("graduate and leave")],
        [data.graduate_continue_count, _t("graduate and continue")],
        [data.graduate_pending_count, _t("become applicants")],
        [data.pending_count, _t("are pending confirmation")],
        [data.missing_count, _t("have no enrollment")],
    ]
        .filter(([count]) => count)
        .map(([count, label]) => `${count} ${label}`);
    return overlayLines(
        _t("Applying the transition…"),
        "",
        ...counts,
        "",
        _t("%s operational record(s) will be deleted.", data.delete_count),
        _t("This can take several minutes — do not close this window."),
    );
}

registry.category("views").add(
    "ems_course_transition_form",
    blockingActionFormView({ action_apply: transitionMessage }),
);
