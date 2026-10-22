/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

// Issue #692: a class on the guard duty board only because its teacher has not checked in. Whoever
// is on guard then, or manages the absence, says either that the teacher is in the classroom after
// all (which checks them in now, see ems.absence_cover.board_mark_present) or goes on to cover the
// class the usual way ('onCover', when they can).
export class GuardUncheckedDialog extends Component {
    static template = "ems.GuardUncheckedDialog";
    static components = { Dialog };
    static props = {
        row: Object,
        line: Object,
        onMarkPresent: Function,
        onCover: { type: Function, optional: true },
        coverLabel: { type: String, optional: true },
        close: Function,
    };

    setup() {
        this.state = useState({ saving: false });
    }

    get title() {
        return _t("%(group)s (%(time)s)", { group: this.props.row.group, time: this.props.line.time_label });
    }

    get body() {
        return _t("%(teacher)s has not checked in yet. If they are in the classroom, their check-in is registered now in your name and they are told.", {
            teacher: this.props.row.teacher,
        });
    }

    async markPresent() {
        this.state.saving = true;
        try {
            await this.props.onMarkPresent();
            this.props.close();
        } finally {
            this.state.saving = false;
        }
    }

    cover() {
        this.props.close();
        this.props.onCover();
    }
}
