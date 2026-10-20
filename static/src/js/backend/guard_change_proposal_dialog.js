/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

// Changes the timetable change the families of a group were told (a longer break, an earlier
// leave...), from a struck-out row of the guard duty board's absences table (issue #659): for
// another change the absences allow, or back to the usual timetable. Whatever is chosen goes out
// as one correction to the group's students and families, never an "undo" followed by a new
// notice. What can be chosen is read from the server when the dialog opens (see
// ems.course.get_change_proposal_options), which checks it all again when sending.
export class GuardChangeProposalDialog extends Component {
    static template = "ems.GuardChangeProposalDialog";
    static components = { Dialog };
    static props = {
        loadOptions: Function,
        onSend: Function,
        close: Function,
    };

    setup() {
        this.state = useState({ data: null, choice: null, saving: false });
        onWillStart(async () => {
            this.state.data = await this.props.loadOptions();
            // The usual timetable, always the last option, until the planner chooses otherwise.
            this.state.choice = this.state.data.options.length - 1;
        });
    }

    get labels() {
        return {
            title: _t("Change proposal"),
            told: _t("The families were told"),
            change: _t("Change it for"),
            help: _t("One correction will be sent to the students and families of %s.", this.state.data.group),
            send: _t("Send correction"),
            cancel: _t("Cancel"),
        };
    }

    choose(index) {
        this.state.choice = index;
    }

    async send() {
        this.state.saving = true;
        try {
            await this.props.onSend(this.state.data.options[this.state.choice]);
            this.props.close();
        } finally {
            this.state.saving = false;
        }
    }
}
