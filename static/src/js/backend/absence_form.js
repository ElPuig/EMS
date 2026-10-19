/** @odoo-module **/

import { registry } from "@web/core/registry";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";

// The decisions on an absence, the Head's (acknowledging it, then validating its supporting
// document) and Direction's. Whoever takes one is working through
// a list of requests, so once it is recorded they are taken back to that list instead of being
// left on a form they are done with. "Documentation insufficient" is left out: it only opens the
// dialog asking for the reason, and the request is sent back once that dialog is confirmed.
const DECISION_BUTTONS = new Set([
    "action_approve",
    "action_validate",
    "action_refuse",
    "action_ems_document_validate",
    "action_ems_direction_done",
    "action_ems_direction_refuse",
]);

export class AbsenceFormController extends FormController {
    setup() {
        super.setup();
        // Every decision ends with the form reloading its record: straight away, or once the
        // dialog it opened first is closed (the message for the requester when the request
        // was corrected, see hr.leave._ems_ask_change_message). So that reload, rather than
        // the button's own return, is where a decision that went through is recognised.
        const load = this.model.load.bind(this.model);
        this.model.load = async (...args) => {
            const result = await load(...args);
            this.goBackAfterDecision();
            return result;
        };
    }

    async beforeExecuteActionButton(clickParams) {
        const proceed = await super.beforeExecuteActionButton(clickParams);
        this.decisionBefore = DECISION_BUTTONS.has(clickParams.name) ? this.decisionState() : null;
        return proceed;
    }

    goBackAfterDecision() {
        // Success is read from the record itself: only a decision that went through changes
        // these states. A refused confirmation, a cancelled dialog or an error leaves them as
        // they were, and the reader stays on the form.
        const before = this.decisionBefore;
        this.decisionBefore = null;
        if (before === null || before === undefined || before === this.decisionState()) {
            return;
        }
        // Opened on its own (a link, a notification) there is no list to go back to, and
        // historyBack() would drop the reader on the home screen instead.
        if (this.env.config.breadcrumbs.length > 1) {
            this.env.config.historyBack();
        }
    }

    decisionState() {
        const { state, ems_document_state, ems_direction_state } = this.model.root.data;
        return `${state}/${ems_document_state}/${ems_direction_state}`;
    }
}

registry.category("views").add("ems_absence_form", {
    ...formView,
    Controller: AbsenceFormController,
});
