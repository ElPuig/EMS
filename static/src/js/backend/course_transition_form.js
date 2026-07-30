/** @odoo-module **/

import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

/**
 * Blocking overlay for the course transition.
 *
 * Applying takes ~24s for a single vocational cycle (127 students) and several
 * minutes for the whole centre, and Odoo alone would only grey the buttons out and
 * show the small "Loading" pill: the operator has no way of telling a long run from
 * a frozen screen. ui.block() is the overlay that already exists for this — nobody
 * was calling it.
 *
 * There is no live counter on purpose. action_apply() runs in a SINGLE transaction,
 * which is what guarantees that a failure half-way leaves the database untouched;
 * bus notifications written inside it are invisible until it commits, so a progress
 * bar would need either to split the run into several transactions (losing that
 * guarantee) or a separate database cursor. Instead the overlay states what the
 * preview has just promised, which is real information the operator has approved.
 */
export class CourseTransitionFormController extends FormController {
    setup() {
        super.setup();
        this.ui = useService("ui");
        this.transitionBlocked = false;
    }

    async beforeExecuteActionButton(clickParams) {
        if (clickParams.name === "action_apply") {
            this.ui.block({ message: this.transitionMessage() });
            this.transitionBlocked = true;
        }
        return super.beforeExecuteActionButton(clickParams);
    }

    async afterExecuteActionButton(clickParams) {
        // useViewButtons calls this even when the action raised (it catches, calls
        // the hook, then re-throws), so a failed apply cannot leave the UI blocked.
        if (this.transitionBlocked) {
            this.ui.unblock();
            this.transitionBlocked = false;
        }
        return super.afterExecuteActionButton(clickParams);
    }

    /** The preview counters, read back from the record the operator is looking at. */
    transitionMessage() {
        const data = this.model.root.data;
        const lines = [
            [data.place_count, _t("join their group")],
            [data.graduate_count, _t("graduate and leave")],
            [data.graduate_continue_count, _t("graduate and continue")],
            [data.graduate_pending_count, _t("become applicants")],
            [data.pending_count, _t("are pending confirmation")],
            [data.missing_count, _t("have no enrollment")],
        ]
            .filter(([count]) => count)
            .map(([count, label]) => `${count} ${label}`);
        // Newlines only render because our CSS puts white-space: pre-line on the
        // BlockUI message, which escapes HTML.
        return [
            _t("Applying the transition…"),
            "",
            ...lines,
            "",
            _t("%s operational record(s) will be deleted.", data.delete_count),
            _t("This can take several minutes — do not close this window."),
        ].join("\n");
    }
}

registry.category("views").add("ems_course_transition_form", {
    ...formView,
    Controller: CourseTransitionFormController,
});
