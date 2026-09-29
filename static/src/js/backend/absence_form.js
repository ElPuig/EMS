/** @odoo-module **/

import { registry } from "@web/core/registry";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";

// The decisions on an absence, the Head's and Direction's. Whoever takes one is working through
// a list of requests, so once it is recorded they are taken back to that list instead of being
// left on a form they are done with.
const DECISION_BUTTONS = new Set([
    "action_approve",
    "action_validate",
    "action_refuse",
    "action_ems_direction_done",
    "action_ems_direction_missing_doc",
    "action_ems_direction_reset",
    "action_ems_direction_refuse",
]);

export class AbsenceFormController extends FormController {
    async beforeExecuteActionButton(clickParams) {
        this.decisionBefore = DECISION_BUTTONS.has(clickParams.name) ? this.decisionState() : null;
        return super.beforeExecuteActionButton(clickParams);
    }

    async afterExecuteActionButton(clickParams) {
        await super.afterExecuteActionButton(clickParams);
        // Odoo calls this hook whether or not the button raised, so success is read from the
        // record itself: the form reloads after a decision that went through, and only then do
        // the states differ. A refused confirmation or an error leaves them as they were, and
        // the reader stays on the form.
        const before = this.decisionBefore;
        this.decisionBefore = null;
        if (before === null || before === this.decisionState()) {
            return;
        }
        // Opened on its own (a link, a notification) there is no list to go back to, and
        // historyBack() would drop the reader on the home screen instead.
        if (this.env.config.breadcrumbs.length > 1) {
            this.env.config.historyBack();
        }
    }

    decisionState() {
        const { state, ems_direction_state } = this.model.root.data;
        return `${state}/${ems_direction_state}`;
    }
}

registry.category("views").add("ems_absence_form", {
    ...formView,
    Controller: AbsenceFormController,
});
