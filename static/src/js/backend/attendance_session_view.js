/** @odoo-module **/

import { Component, useState, onWillStart, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";
import { _t } from "@web/core/l10n/translation";


class AttendanceSessionView extends Component {
    static template = "ems.AttendanceSessionView";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.statuses = [];   // populated in onWillStart from model fields_get

        this.notesDialog   = useRef("notesDialog");
        this.notesTextarea = useRef("notesTextarea");
        this._lastnameMap  = {};

        this.state = useState({
            date: this._todayStr(),
            sessions: [],
            planned: [],
            groups: [],          // string[] — group names present in today's sessions/schedules
            selectedGroup: null, // null = All
            selected: null,      // "session_<id>" or "schedule_<id>"
            lines: [],
            loading: true,
            saving: {},
            editingLineId: null,
            editingStudentName: "",
            sortField: 'lastname',  // 'lastname' | 'name'
            sortDir:   'asc',       // 'asc' | 'desc'
            guardMode: false,
        });

        onWillStart(async () => {
            await this._loadStatuses();
            await this._loadAll();
        });
    }

    // ── Date helpers ─────────────────────────────────────────────────────────

    _todayStr() {
        const d = new Date();
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    }

    _shiftDate(dateStr, days) {
        const [y, m, d] = dateStr.split("-").map(Number);
        const dt = new Date(y, m - 1, d + days);
        return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;
    }

    _weekdayStr(dateStr) {
        const [y, m, d] = dateStr.split("-").map(Number);
        return String((new Date(y, m - 1, d).getDay() + 6) % 7);
    }

    formatDate(dateStr) {
        const [y, m, d] = dateStr.split("-").map(Number);
        return new Date(y, m - 1, d).toLocaleDateString("es-ES", {
            weekday: "long", day: "numeric", month: "long", year: "numeric",
        });
    }

    // ── Data loading ──────────────────────────────────────────────────────────

    async _loadStatuses() {
        const info = await this.orm.call(
            "ems.attendance_session_line", "fields_get", [["status"]], { attributes: ["selection"] }
        );
        this.statuses = info.status.selection.map(([key, title]) => ({
            key,
            title,
            label: title.split(/\s+/).slice(0, 2).map(w => w[0]).join('').toUpperCase(),
        }));
    }

    async _loadAll() {
        this.state.loading = true;

        if (this.state.guardMode) {
            await this._loadAllGuard();
        } else {
            await this._loadAllNormal();
        }

        await this._autoSelect();
        this.state.loading = false;
    }

    async _loadAllNormal() {
        // Admins bypass security rules, so we need an explicit teacher filter for both
        // sessions and schedules. Non-admin teachers rely on record rules.
        let teacherIds = [];
        if (session.is_admin || session.is_system) {
            const employees = await this.orm.searchRead(
                "hr.employee", [["user_id", "=", session.uid]], ["id"]
            );
            teacherIds = employees.map(e => e.id);
        }

        // 1. Existing session headers for this date
        const sessionDomain = [["date", "=", this.state.date]];
        if (teacherIds.length) {
            sessionDomain.push(
                "|",
                ["template_teacher_id", "in", teacherIds],
                ["session_teacher_id", "in", teacherIds],
            );
        }
        const sessions = await this.orm.searchRead(
            "ems.attendance_session_header",
            sessionDomain,
            ["id", "time_range", "subject_id", "study_id", "attendance_schedule_id",
             "attendance_session_line_ids", "start_time", "end_time"],
            { order: "start_time asc" }
        );

        // 2. Schedules for this weekday (admin needs explicit filter; teachers use security rules)
        const weekday = this._weekdayStr(this.state.date);
        const scheduleDomain = [
            ["weekday", "=", weekday],
            ["start_date", "<=", this.state.date],
            ["end_date", ">=", this.state.date],
        ];
        if (teacherIds.length) {
            scheduleDomain.push(["attendance_template_id.teacher_id", "in", teacherIds]);
        }
        const schedules = await this.orm.searchRead(
            "ems.attendance_schedule",
            scheduleDomain,
            ["id", "name", "time_range", "attendance_template_id", "start_time", "end_time"],
            { order: "start_time asc" }
        );

        // 3. Fetch extra schedules linked to existing sessions not in today's planned list
        const plannedScheduleIds = new Set(schedules.map(s => s.id));
        const extraScheduleIds = sessions
            .filter(s => s.attendance_schedule_id && !plannedScheduleIds.has(s.attendance_schedule_id[0]))
            .map(s => s.attendance_schedule_id[0]);

        let extraSchedules = [];
        if (extraScheduleIds.length) {
            extraSchedules = await this.orm.searchRead(
                "ems.attendance_schedule",
                [["id", "in", extraScheduleIds]],
                ["id", "name", "attendance_template_id"]
            );
        }

        this.state.sessions = sessions;

        // 4. Keep only schedules without an existing header for this date
        const usedScheduleIds = new Set(
            sessions.filter(s => s.attendance_schedule_id).map(s => s.attendance_schedule_id[0])
        );
        this.state.planned = schedules.filter(s => !usedScheduleIds.has(s.id));

        // Build a scheduleId → name map for sessions whose schedule wasn't in today's planned list
        const extraScheduleNameMap = Object.fromEntries(extraSchedules.map(s => [s.id, s.name]));

        // 5. Build the group selector from schedule names (format: "Subject (Group) | ...")
        const allGroups = new Set([
            ...this.state.sessions.map(s => {
                if (!s.attendance_schedule_id) return '';
                const name = s.attendance_schedule_id[1] || extraScheduleNameMap[s.attendance_schedule_id[0]] || '';
                return this._groupFromScheduleName(name);
            }),
            ...this.state.planned.map(s => this._groupFromScheduleName(s.name || '')),
        ]);
        allGroups.delete('');
        this.state.groups = [...allGroups].sort();

        // Reset group filter when changing day (new day may have different groups)
        this.state.selectedGroup = null;
    }

    async _loadAllGuard() {
        // Guard mode: fetch all sessions and planned schedules for today via sudo() on the server.
        this.state.date = this._todayStr();
        const now = this._nowAsFloat();
        const [allSessions, allPlanned] = await Promise.all([
            this.orm.call("ems.attendance_session_header", "get_guard_sessions", [this.state.date]),
            this.orm.call("ems.attendance_session_header", "get_guard_planned",  [this.state.date]),
        ]);
        // Guard mode: only show sessions and planned schedules for the current time slot.
        const sessions = allSessions.filter(s => s.start_time <= now && now < s.end_time);
        const planned  = allPlanned.filter(s => s.start_time <= now && now < s.end_time);
        this.state.sessions = sessions;
        this.state.planned  = planned;

        const allGroups = new Set([
            ...sessions.map(s => this._groupFromScheduleName(s.attendance_schedule_id ? s.attendance_schedule_id[1] : '')),
            ...planned.map(s => this._groupFromScheduleName(s.name || '')),
        ]);
        allGroups.delete('');
        this.state.groups = [...allGroups].sort();
        this.state.selectedGroup = null;
    }

    async _loadLines(sessionId) {
        if (!sessionId) { this.state.lines = []; return; }
        const lines = await this.orm.searchRead(
            "ems.attendance_session_line",
            [["attendance_session_id", "=", sessionId]],
            ["id", "student_id", "status", "notes"],
        );

        // Fetch lastnames to allow client-side sorting
        const partnerIds = lines.filter(l => l.student_id).map(l => l.student_id[0]);
        if (partnerIds.length) {
            const partners = await this.orm.searchRead(
                "res.partner", [["id", "in", partnerIds]], ["id", "lastname"]
            );
            this._lastnameMap = Object.fromEntries(partners.map(p => [p.id, p.lastname || ""]));
        } else {
            this._lastnameMap = {};
        }

        this.state.lines = this._sortedLines(lines);
        this.state.saving = {};
    }

    _sortedLines(lines) {
        const { sortField, sortDir } = this.state;
        const dir = sortDir === "asc" ? 1 : -1;
        const locale = { sensitivity: "base" };
        return [...lines].sort((a, b) => {
            const va = sortField === "lastname"
                ? (a.student_id ? (this._lastnameMap[a.student_id[0]] || "") : "")
                : (a.student_id ? a.student_id[1] : "");
            const vb = sortField === "lastname"
                ? (b.student_id ? (this._lastnameMap[b.student_id[0]] || "") : "")
                : (b.student_id ? b.student_id[1] : "");
            return dir * va.localeCompare(vb, undefined, locale);
        });
    }

    onSortChange(ev) {
        const [field, dir] = ev.target.value.split(":");
        this.state.sortField = field;
        this.state.sortDir   = dir;
        this.state.lines     = this._sortedLines(this.state.lines);
    }

    _nowAsFloat() {
        const now = new Date();
        return now.getHours() + now.getMinutes() / 60;
    }

    async _autoSelect() {
        const sessions = this.filteredSessions;
        const planned = this.filteredPlanned;

        // Keep current selection if it's still visible after filtering
        const currentValid = this.state.selected && (
            sessions.some(s => `session_${s.id}` === this.state.selected) ||
            planned.some(s => `schedule_${s.id}` === this.state.selected)
        );
        if (currentValid) return;

        // When viewing today, prefer the session/schedule currently running
        let bestSession = null;
        let bestSchedule = null;
        if (this.state.date === this._todayStr()) {
            const now = this._nowAsFloat();
            bestSession = sessions.find(s => s.start_time <= now && now < s.end_time) || null;
            if (!bestSession) {
                bestSchedule = planned.find(s => s.start_time <= now && now < s.end_time) || null;
            }
        }

        const targetSession = bestSession || (sessions.length ? sessions[0] : null);
        const targetSchedule = !targetSession && (bestSchedule || (planned.length ? planned[0] : null));

        if (targetSession) {
            this.state.selected = `session_${targetSession.id}`;
            await this._loadLines(targetSession.id);
        } else if (targetSchedule) {
            this.state.selected = `schedule_${targetSchedule.id}`;
            this.state.lines = [];
        } else {
            this.state.selected = null;
            this.state.lines = [];
        }
    }

    // ── Translatable strings ──────────────────────────────────────────────────

    get todayStr() { return this._todayStr(); }

    get strings() {
        return {
            allGroups:         _t("All groups"),
            sessions:          _t("Sessions"),
            planned:           _t("Planned (no session)"),
            noSessionsDay:     _t("No sessions or scheduled timetables for this day."),
            sessionNotStarted: _t("This session has not been started for the selected day."),
            startSession:      _t("Start session"),
            noStudents:        _t("This session has no students."),
            notesPlaceholder:  _t("Notes for this student..."),
            addNotes:          _t("Add notes"),
            cancel:            _t("Cancel"),
            save:              _t("Save"),
            lastnameAZ:        _t("Lastname A→Z"),
            lastnameZA:        _t("Lastname Z→A"),
            nameAZ:            _t("Name A→Z"),
            nameZA:            _t("Name Z→A"),
            guardMode:         _t("Guard mode"),
        };
    }

    // ── Filtered getters (reactive — depend on state.selectedGroup) ──────────

    get filteredSessions() {
        if (!this.state.selectedGroup) return this.state.sessions;
        return this.state.sessions.filter(s => {
            const g = this._groupFromScheduleName(
                s.attendance_schedule_id ? s.attendance_schedule_id[1] : ''
            );
            return g === this.state.selectedGroup;
        });
    }

    get filteredPlanned() {
        if (!this.state.selectedGroup) return this.state.planned;
        return this.state.planned.filter(s =>
            this._groupFromScheduleName(s.name || '') === this.state.selectedGroup
        );
    }

    get selectedSession() {
        if (!this.state.selected?.startsWith("session_")) return null;
        const id = parseInt(this.state.selected.split("_")[1]);
        return this.filteredSessions.find(s => s.id === id) || null;
    }

    get selectedSchedule() {
        if (!this.state.selected?.startsWith("schedule_")) return null;
        const id = parseInt(this.state.selected.split("_")[1]);
        return this.filteredPlanned.find(s => s.id === id) || null;
    }

    _groupFromScheduleName(name) {
        const m = name && name.match(/\(([^)]+)\)/);
        return m ? m[1] : '';
    }

    sessionLabel(s) {
        return s.attendance_schedule_id ? s.attendance_schedule_id[1] : s.time_range;
    }

    scheduleLabel(s) {
        return s.name || s.time_range;
    }

    avatarUrl(line) {
        return line.student_id
            ? `/web/image/res.partner/${line.student_id[0]}/image_128`
            : "/web/static/img/placeholder.png";
    }

    // ── Event handlers ────────────────────────────────────────────────────────

    async prevDay() {
        this.state.date = this._shiftDate(this.state.date, -1);
        await this._loadAll();
    }

    async nextDay() {
        const next = this._shiftDate(this.state.date, 1);
        if (next > this._todayStr()) return;
        this.state.date = next;
        await this._loadAll();
    }

    async onDateInput(ev) {
        const today = this._todayStr();
        const val = ev.target.value || today;
        this.state.date = val > today ? today : val;
        await this._loadAll();
    }

    onGroupChange(ev) {
        this.state.selectedGroup = ev.target.value || null;
        this._autoSelect();
    }

    async onSelectorChange(ev) {
        this.state.selected = ev.target.value;
        if (this.selectedSession) {
            await this._loadLines(this.selectedSession.id);
        } else {
            this.state.lines = [];
        }
    }

    async onGuardModeChange(ev) {
        this.state.guardMode = ev.target.checked;
        await this._loadAll();
    }

    async onStatusClick(lineId, status) {
        if (this.state.saving[lineId]) return;
        this.state.saving[lineId] = true;
        try {
            if (this.state.guardMode) {
                await this.orm.call(
                    "ems.attendance_session_header", "write_guard_session_line",
                    [lineId, { status }]
                );
            } else {
                await this.orm.write("ems.attendance_session_line", [lineId], { status });
            }
            const line = this.state.lines.find(l => l.id === lineId);
            if (line) line.status = status;
        } finally {
            this.state.saving[lineId] = false;
        }
    }

    onNotesClick(lineId, studentName, notes) {
        this.state.editingLineId = lineId;
        this.state.editingStudentName = studentName;
        this.notesTextarea.el.value = notes || "";
        this.notesDialog.el.showModal();
        this.notesTextarea.el.focus();
    }

    onNotesCancel() {
        this.notesDialog.el.close();
        this.state.editingLineId = null;
    }

    async onNotesSave() {
        const lineId = this.state.editingLineId;
        const notes = this.notesTextarea.el.value.trim();
        if (this.state.guardMode) {
            await this.orm.call(
                "ems.attendance_session_header", "write_guard_session_line",
                [lineId, { notes: notes || false }]
            );
        } else {
            await this.orm.write("ems.attendance_session_line", [lineId], { notes: notes || false });
        }
        const line = this.state.lines.find(l => l.id === lineId);
        if (line) line.notes = notes || false;
        this.notesDialog.el.close();
        this.state.editingLineId = null;
    }

    async onStartSession(scheduleId) {
        this.state.loading = true;
        try {
            const [newId] = await this.orm.create("ems.attendance_session_header", [{
                date: this.state.date,
                attendance_schedule_id: scheduleId,
                mode: "scheduled",
            }]);
            await this._loadAll();
            this.state.selected = "session_" + newId;
            await this._loadLines(newId);
        } finally {
            this.state.loading = false;
        }
    }
}

registry.category("actions").add("ems_attendance_session_view", AttendanceSessionView);
