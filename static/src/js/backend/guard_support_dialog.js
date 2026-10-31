/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

// Sends a guard teacher, from their badge in the guard column of the guard duty board's absences
// table, to support a teacher who is in class (issue #725). Offers the classes of the guard's
// period whose teacher is in and whose absences the user manages (see
// ems.course._get_support_options, which the server checks again on save), with a message for
// them. Saving tells the guard and the teacher; the support the guard already gives then can be
// removed, which tells them too.
export class GuardSupportDialog extends Component {
    static template = "ems.GuardSupportDialog";
    static components = { Dialog };
    static props = {
        guard: Object,
        line: Object,
        loadOptions: Function,
        onSend: Function,
        onRelease: Function,
        close: Function,
    };

    setup() {
        this.state = useState({ options: [], current: [], choice: false, message: "", loaded: false, saving: false });
        onWillStart(async () => {
            const { options, current } = await this.props.loadOptions();
            Object.assign(this.state, {
                options, current, loaded: true, choice: options.length === 1 ? this.optionKey(options[0]) : false,
            });
        });
    }

    get title() {
        return _t("Send %(guard)s as support (%(time)s)", { guard: this.props.guard.name, time: this.props.line.time_label });
    }

    get labels() {
        return {
            current: _t("Currently supporting"),
            classes: _t("Class to support"),
            noOptions: _t("There is no class you manage in this period whose teacher is in."),
            message: _t("Message for the guard and the teacher"),
            placeholder: _t("What the support is needed for..."),
            send: _t("Send and notify"),
            removeSupport: _t("Remove support"),
            cancel: _t("Cancel"),
        };
    }

    optionKey(option) {
        return `${option.group_id}-${option.teacher_id}`;
    }

    optionLabel(option) {
        const details = [option.subject, option.room, option.time].filter(Boolean).join(" · ");
        return _t("%(group)s - %(teacher)s (%(details)s)", { group: option.group, teacher: option.teacher, details });
    }

    get selected() {
        return this.state.options.find((option) => this.optionKey(option) === this.state.choice);
    }

    async send() {
        this.state.saving = true;
        try {
            await this.props.onSend(this.selected, this.state.message);
            this.props.close();
        } finally {
            this.state.saving = false;
        }
    }

    async release(coverId) {
        this.state.saving = true;
        try {
            await this.props.onRelease(coverId);
            this.props.close();
        } finally {
            this.state.saving = false;
        }
    }
}
