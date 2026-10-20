/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { GuardArrangementPlan, fullPlanSelection, toggledPlanSelection } from "./guard_arrangement_plan";

// Changes the timetable change the families of a group were told (a longer break, an earlier
// leave...), from a struck-out row of the guard duty board's absences table (issue #659): for
// another change the absences allow, back to the usual timetable, or an internal arrangement of
// the group's day planned as if nothing had been told (its correction is one of its steps).
// Whatever is chosen goes out as one correction to the group's students and families, never an
// "undo" followed by a new notice. What can be chosen is read from the server when the dialog opens (see
// ems.course.get_change_proposal_options), which checks it all again when sending.
export class GuardChangeProposalDialog extends Component {
    static template = "ems.GuardChangeProposalDialog";
    static components = { Dialog, GuardArrangementPlan };
    static props = {
        loadOptions: Function,
        onSend: Function,
        onApplyPlan: Function,
        close: Function,
    };

    setup() {
        this.state = useState({ data: null, choice: null, selections: [], saving: false });
        onWillStart(async () => {
            this.state.data = await this.props.loadOptions();
            this.state.selections = this.state.data.plans.map(fullPlanSelection);
            // The usual timetable, always the last option, until the planner chooses otherwise.
            this.state.choice = `change-${this.state.data.options.length - 1}`;
        });
    }

    get labels() {
        return {
            title: _t("Change proposal"),
            told: _t("The families were told"),
            change: _t("Change it for"),
            plans: _t("Or rearrange the lessons"),
            help: _t("One correction will be sent to the students and families of %s.", this.state.data.group),
            send: _t("Send correction"),
            cancel: _t("Cancel"),
        };
    }

    choose(choice) {
        this.state.choice = choice;
    }

    togglePlanStep(planIndex, index, checked) {
        const plan = this.state.data.plans[planIndex];
        this.state.selections[planIndex] = toggledPlanSelection(plan, this.state.selections[planIndex], index, checked);
    }

    get canSend() {
        const [kind, index] = this.state.choice.split("-");
        return !this.state.saving && (kind !== "plan" || this.state.selections[index].some(Boolean));
    }

    async send() {
        this.state.saving = true;
        try {
            const [kind, index] = this.state.choice.split("-");
            if (kind === "plan") {
                await this.props.onApplyPlan(this.state.data.plans[index], this.state.selections[index], this.state.data.reopen);
            } else {
                await this.props.onSend(this.state.data.options[index]);
            }
            this.props.close();
        } finally {
            this.state.saving = false;
        }
    }
}
