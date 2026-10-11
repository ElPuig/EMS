/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

// Resolves a class left without its teacher, from a row of the guard duty board's absences table:
// - With one of the internal arrangements the board detected (issue #605, see
//   ems.course._get_arrangement_options), offered first, swaps before moved lessons: the students
//   should lose as few lessons as possible. A moved lesson changes the group's day, so saving it
//   opens the notice for the families, and it only counts once that notice is sent.
// - By sending a guard teacher (issue #571). Only the guards on duty in that row are offered (see
//   ems.course._get_guard_candidates, which the server checks again on save), with a free-text
//   message for them. Saving notifies the guard; removing an assignment tells them they are no
//   longer needed.
// - With an arrangement the board cannot work out (two groups joined for the same subject...),
//   described by hand so that it is on record, with the teacher involved if there is one.
export class GuardCoverDialog extends Component {
    static template = "ems.GuardCoverDialog";
    static components = { Dialog };
    static props = {
        row: Object,
        line: Object,
        onAssign: Function,
        onArrange: Function,
        loadArrangementCandidates: Function,
        onOpenNotice: { type: Function, optional: true },
        onRelease: Function,
        close: Function,
    };

    setup() {
        const { cover, arrangement } = this.props.row;
        const candidates = this.props.line.guard_candidates;
        this.state = useState({
            mode: this.initialMode(),
            guardId: cover ? cover.guard_id : candidates.length === 1 ? candidates[0].id : false,
            message: cover ? cover.message : "",
            teacherId: arrangement && arrangement.type === "manual" ? arrangement.teacher_id : false,
            note: arrangement && arrangement.type === "manual" ? arrangement.note : "",
            manualCandidates: [],
            saving: false,
        });
        if (this.state.mode === "manual") {
            this.loadManualCandidates();
        }
    }

    initialMode() {
        const { cover, arrangement, arrangement_options: options } = this.props.row;
        if (arrangement) {
            return arrangement.type === "manual" ? "manual" : "current";
        }
        if (cover || !options.length) {
            return "guard";
        }
        return "option-0";
    }

    get title() {
        return _t("Cover %(group)s (%(time)s)", { group: this.props.row.group, time: this.props.line.time_label });
    }

    get labels() {
        return {
            absent: _t("Absent teacher"),
            options: _t("Possible arrangements"),
            current: _t("Current arrangement"),
            modeGuard: _t("Send a guard teacher"),
            modeManual: _t("Other arrangement (described by hand)"),
            guard: _t("Guard teacher"),
            choose: _t("Choose a guard teacher..."),
            noCandidates: _t("Nobody is on guard duty in this period."),
            message: _t("Message for the guard teacher"),
            placeholder: _t("What the students have to work on, where to find the materials..."),
            teacher: _t("Teacher involved (optional)"),
            noTeacher: _t("Nobody in particular"),
            note: _t("Arrangement"),
            notePlaceholder: _t("E.g. groups A and B are joined for this lesson and leave at 13:25."),
            pending: _t("This arrangement is waiting for its notice to the families to be sent."),
            openNotice: _t("Open notice"),
            assign: _t("Assign and notify"),
            apply: _t("Apply and notify"),
            arrange: _t("Save arrangement"),
            release: this.props.row.arrangement ? _t("Remove arrangement") : _t("Remove assignment"),
            cancel: _t("Cancel"),
        };
    }

    // How many classes each guard has covered this course (issue #600), so the planner can share
    // the covers out fairly.
    candidateLabel(candidate) {
        return _t("%(name)s (%(count)s covered this course)", { name: candidate.name, count: candidate.cover_count });
    }

    noticeLabel(option) {
        return _t("The families will be told: %s", option.change_label);
    }

    get selectedOption() {
        const mode = this.state.mode;
        return mode.startsWith("option-") ? this.props.row.arrangement_options[Number(mode.slice(7))] : null;
    }

    get saveLabel() {
        if (this.state.mode === "guard") {
            return this.labels.assign;
        }
        return this.state.mode === "manual" ? this.labels.arrange : this.labels.apply;
    }

    get canSave() {
        if (this.state.saving || this.state.mode === "current") {
            return false;
        }
        if (this.state.mode === "guard") {
            return Boolean(this.state.guardId);
        }
        if (this.state.mode === "manual") {
            return Boolean(this.state.note.trim());
        }
        return true;
    }

    async loadManualCandidates() {
        if (!this.state.manualCandidates.length) {
            this.state.manualCandidates = await this.props.loadArrangementCandidates();
        }
    }

    async onModeChange(mode) {
        this.state.mode = mode;
        if (mode === "manual") {
            await this.loadManualCandidates();
        }
    }

    onGuardChange(ev) {
        this.state.guardId = Number(ev.target.value) || false;
    }

    onTeacherChange(ev) {
        this.state.teacherId = Number(ev.target.value) || false;
    }

    async save() {
        this.state.saving = true;
        try {
            const option = this.selectedOption;
            if (this.state.mode === "guard") {
                await this.props.onAssign(this.state.guardId, this.state.message);
            } else if (option) {
                await this.props.onArrange(option.type, option.teacher_id, false, option);
            } else {
                await this.props.onArrange("manual", this.state.teacherId, this.state.note, null);
            }
            this.props.close();
        } finally {
            this.state.saving = false;
        }
    }

    async openNotice() {
        this.props.close();
        await this.props.onOpenNotice();
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
