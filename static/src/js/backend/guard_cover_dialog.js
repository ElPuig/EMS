/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

// Resolves a class left without its teacher, from a row of the guard duty board's absences table,
// in one of two ways:
// - Send a guard teacher to it (issue #571). Only the guards on duty in that row are offered (see
//   ems.course._get_guard_candidates, which the server checks again on save), with a free-text
//   message for them - what the students have to work on, where the materials are... Saving
//   notifies the guard; removing an assignment tells them they are no longer needed.
// - Record an internal arrangement (issue #605): the teachers rearranged themselves (two of them
//   swap lessons, one moves a lesson earlier...) and nobody has to cover it. The planner picks who
//   is with the group instead (see ems.course.get_arrangement_candidates), describes the movement
//   and, if it leaves one of that teacher's lessons with the group free, which one: when that
//   changes the group's day, the notice for the families is prepared on saving and the
//   arrangement only counts once it is sent.
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
        const cover = this.props.row.cover;
        const arrangement = this.props.row.arrangement;
        const candidates = this.props.line.guard_candidates;
        this.state = useState({
            mode: arrangement ? "arrangement" : "guard",
            guardId: cover ? cover.guard_id : candidates.length === 1 ? candidates[0].id : false,
            message: cover ? cover.message : "",
            teacherId: arrangement ? arrangement.teacher_id : false,
            note: arrangement ? arrangement.note : "",
            vacatedIndex: -1,
            arrangementCandidates: [],
            saving: false,
        });
        onWillStart(async () => {
            if (arrangement) {
                await this.loadArrangementCandidates();
            }
        });
    }

    get title() {
        return _t("Cover %(group)s (%(time)s)", { group: this.props.row.group, time: this.props.line.time_label });
    }

    get labels() {
        return {
            absent: _t("Absent teacher"),
            modeGuard: _t("Send a guard teacher"),
            modeArrangement: _t("No guard needed: internal arrangement"),
            guard: _t("Guard teacher"),
            choose: _t("Choose a guard teacher..."),
            noCandidates: _t("Nobody is on guard duty in this period."),
            message: _t("Message for the guard teacher"),
            placeholder: _t("What the students have to work on, where to find the materials..."),
            teacher: _t("Teacher who will be with the group"),
            chooseTeacher: _t("Choose a teacher..."),
            noTeachers: _t("No teacher is free in this period."),
            teachesGroup: _t("teaches this group"),
            onGuard: _t("on guard duty"),
            note: _t("Arrangement"),
            notePlaceholder: _t("E.g. they swap lessons: the absent teacher teaches the group at 9:00 instead."),
            vacated: _t("Lesson of theirs with this group left free"),
            noVacated: _t("None (they swap or the lesson is not moved)"),
            vacatedHelp: _t("If the free lesson lets the group come in later or leave earlier, the notice for the families is prepared on saving, and the arrangement only counts once it is sent."),
            pending: _t("This arrangement is waiting for its notice to the families to be sent."),
            openNotice: _t("Open notice"),
            assign: _t("Assign and notify"),
            arrange: _t("Save arrangement"),
            release: this.props.row.arrangement ? _t("Remove arrangement") : _t("Remove assignment"),
            cancel: _t("Cancel"),
        };
    }

    get selectedTeacher() {
        return this.state.arrangementCandidates.find((candidate) => candidate.id === this.state.teacherId);
    }

    get canSave() {
        if (this.state.saving) {
            return false;
        }
        if (this.state.mode === "guard") {
            return Boolean(this.state.guardId);
        }
        return Boolean(this.state.teacherId && this.state.note.trim());
    }

    candidateLabel(candidate) {
        const tags = [];
        if (candidate.teaches_group) {
            tags.push(this.labels.teachesGroup);
        }
        if (candidate.on_guard) {
            tags.push(this.labels.onGuard);
        }
        return tags.length ? `${candidate.name} (${tags.join(", ")})` : candidate.name;
    }

    async loadArrangementCandidates() {
        this.state.arrangementCandidates = await this.props.loadArrangementCandidates();
        const arrangement = this.props.row.arrangement;
        if (arrangement && this.selectedTeacher) {
            this.state.vacatedIndex = this.selectedTeacher.lessons.findIndex(
                (lesson) => Math.abs(lesson.hour_from - arrangement.vacated_hour_from) < 0.01 && arrangement.vacated_hour_to
            );
        }
    }

    async onModeChange(mode) {
        this.state.mode = mode;
        if (mode === "arrangement" && !this.state.arrangementCandidates.length) {
            await this.loadArrangementCandidates();
        }
    }

    onGuardChange(ev) {
        this.state.guardId = Number(ev.target.value) || false;
    }

    onTeacherChange(ev) {
        this.state.teacherId = Number(ev.target.value) || false;
        this.state.vacatedIndex = -1;
    }

    onVacatedChange(ev) {
        this.state.vacatedIndex = Number(ev.target.value);
    }

    async save() {
        this.state.saving = true;
        try {
            if (this.state.mode === "guard") {
                await this.props.onAssign(this.state.guardId, this.state.message);
            } else {
                const lessons = this.selectedTeacher ? this.selectedTeacher.lessons : [];
                await this.props.onArrange(this.state.teacherId, this.state.note, lessons[this.state.vacatedIndex]);
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
