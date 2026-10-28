/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { GuardArrangementPlan, fullPlanSelection, toggledPlanSelection } from "./guard_arrangement_plan";

// Resolves a class left without its teacher, from a row of the guard duty board's absences table:
// - With one of the internal arrangement plans the board detected that resolve it (issues #605,
//   #645, see ems.course._get_arrangement_plans), offered first, the best first: the students
//   should lose as few lessons as possible. The planner may keep only some of its steps. A notice
//   among them opens for the families, and the moves it frees the group from only count once it
//   is sent.
// - By sending a guard teacher (issue #571). Only the guards on duty during the class are offered,
//   those covering all of it first and then those whose guard duty only overlaps part of it, with
//   the part each one would cover (issue #637; see ems.course._guard_spans, which the server
//   checks again on save), and a free-text message for them. Saving notifies the guard; several
//   can each cover part of the class, and each assignment can be removed on its own, which tells
//   that guard they are no longer needed.
// - With an arrangement the board cannot work out (two groups joined for the same subject...),
//   described by hand so that it is on record, with the teacher involved if there is one.
export class GuardCoverDialog extends Component {
    static template = "ems.GuardCoverDialog";
    static components = { Dialog, GuardArrangementPlan };
    static props = {
        row: Object,
        line: Object,
        // Opened right after applying a plan that leaves this class to a guard (issue #710): only
        // sending a guard is offered, never another arrangement.
        guardOnly: { type: Boolean, optional: true },
        onAssign: Function,
        onApplyPlan: Function,
        onArrange: Function,
        loadArrangementCandidates: Function,
        onOpenNotice: { type: Function, optional: true },
        onRelease: Function,
        close: Function,
    };

    setup() {
        const { covers, arrangement } = this.props.row;
        const candidates = this.props.line.guard_candidates;
        // The guard already covering the whole class, to re-send their message; with a part still
        // missing, the planner is choosing somebody else, so nobody is preselected.
        const only = covers.length === 1 && !this.props.row.missing.length ? covers[0] : null;
        this.state = useState({
            mode: this.initialMode(),
            guardId: only ? only.guard_id : !covers.length && candidates.length === 1 ? candidates[0].id : false,
            message: only ? only.message : "",
            teacherId: arrangement && arrangement.type === "manual" ? arrangement.teacher_id : false,
            note: arrangement && arrangement.type === "manual" ? arrangement.note : "",
            manualCandidates: [],
            selections: this.props.row.arrangement_plans.map(fullPlanSelection),
            saving: false,
        });
        if (this.state.mode === "manual") {
            this.loadManualCandidates();
        }
    }

    initialMode() {
        const { covers, arrangement, arrangement_plans: plans } = this.props.row;
        if (arrangement) {
            return arrangement.type === "manual" ? "manual" : "current";
        }
        if (covers.length || !plans.length || this.props.guardOnly) {
            return "guard";
        }
        return "plan-0";
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
            apply: _t("Apply the checked steps"),
            arrange: _t("Save arrangement"),
            release: _t("Remove arrangement"),
            assigned: _t("Guards assigned"),
            removeCover: _t("Remove assignment"),
            cancel: _t("Cancel"),
        };
    }

    // How many classes each guard has covered this course (issue #600), so the planner can share
    // the covers out fairly.
    // A guard whose duty only overlaps part of the class says which part (issue #637).
    candidateLabel(candidate) {
        if (candidate.partial) {
            return _t("%(name)s - %(time)s, part of the class (%(count)s covered this course)", {
                name: candidate.name, time: candidate.label, count: candidate.cover_count,
            });
        }
        return _t("%(name)s (%(count)s covered this course)", { name: candidate.name, count: candidate.cover_count });
    }

    get selectedPlanIndex() {
        const mode = this.state.mode;
        return mode.startsWith("plan-") ? Number(mode.slice(5)) : null;
    }

    togglePlanStep(planIndex, index, checked) {
        const plan = this.props.row.arrangement_plans[planIndex];
        this.state.selections[planIndex] = toggledPlanSelection(plan, this.state.selections[planIndex], index, checked);
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
        return this.state.selections[this.selectedPlanIndex].some(Boolean);
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
            const planIndex = this.selectedPlanIndex;
            if (this.state.mode === "guard") {
                await this.props.onAssign(this.state.guardId, this.state.message);
            } else if (planIndex !== null) {
                if (!(await this.props.onApplyPlan(this.props.row.arrangement_plans[planIndex], this.state.selections[planIndex]))) {
                    return;  // cancelled: the planner may change the steps
                }
            } else {
                await this.props.onArrange(this.state.teacherId, this.state.note);
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

    async release(coverId = false) {
        this.state.saving = true;
        try {
            await this.props.onRelease(coverId);
            this.props.close();
        } finally {
            this.state.saving = false;
        }
    }
}
