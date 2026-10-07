/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

// Sends a guard teacher to a class left without its teacher (issue #571), from a row of the guard
// duty board's absences table. Only the guards on duty in that row are offered (see
// ems.course._get_guard_candidates, which the server checks again on save), with a free-text
// message for them - what the students have to work on, where the materials are... Saving
// notifies the guard; removing an assignment tells them they are no longer needed.
export class GuardCoverDialog extends Component {
    static template = "ems.GuardCoverDialog";
    static components = { Dialog };
    static props = {
        row: Object,
        line: Object,
        onAssign: Function,
        onRelease: Function,
        close: Function,
    };

    setup() {
        const cover = this.props.row.cover;
        const candidates = this.props.line.guard_candidates;
        this.state = useState({
            guardId: cover ? cover.guard_id : candidates.length === 1 ? candidates[0].id : false,
            message: cover ? cover.message : "",
            saving: false,
        });
    }

    get title() {
        return _t("Cover %(group)s (%(time)s)", { group: this.props.row.group, time: this.props.line.time_label });
    }

    get labels() {
        return {
            absent: _t("Absent teacher"),
            guard: _t("Guard teacher"),
            choose: _t("Choose a guard teacher..."),
            noCandidates: _t("Nobody is on guard duty in this period."),
            message: _t("Message for the guard teacher"),
            placeholder: _t("What the students have to work on, where to find the materials..."),
            assign: _t("Assign and notify"),
            release: _t("Remove assignment"),
            cancel: _t("Cancel"),
        };
    }

    onGuardChange(ev) {
        this.state.guardId = Number(ev.target.value) || false;
    }

    async assign() {
        this.state.saving = true;
        try {
            await this.props.onAssign(this.state.guardId, this.state.message);
            this.props.close();
        } finally {
            this.state.saving = false;
        }
    }

    async release() {
        this.state.saving = true;
        try {
            await this.props.onRelease();
            this.props.close();
        } finally {
            this.state.saving = false;
        }
    }
}
