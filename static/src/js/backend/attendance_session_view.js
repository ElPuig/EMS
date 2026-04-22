/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";

const STATUS_CONFIG = [
    { key: "a_attended",  label: "A", color: "#00b269", title: "Attended"  },
    { key: "a_delayed",   label: "R", color: "#f07800", title: "Delayed"   },
    { key: "m_miss",      label: "F", color: "#e74c3c", title: "Miss"      },
    { key: "m_justified", label: "J", color: "#4a90d9", title: "Justified" },
    { key: "a_issue",     label: "I", color: "#9b59b6", title: "Issue"     },
];

class AttendanceSessionView extends Component {
    static template = "ems.AttendanceSessionView";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.statuses = STATUS_CONFIG;

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
        });

        onWillStart(async () => {
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

    async _loadAll() {
        this.state.loading = true;

        // 1. Existing session headers for this date
        const sessions = await this.orm.searchRead(
            "ems.attendance_session_header",
            [["date", "=", this.state.date]],
            ["id", "time_range", "subject_id", "study_id", "attendance_schedule_id",
             "attendance_session_line_ids"],
            { order: "start_time asc" }
        );

        // 2. Schedules for this weekday (admin needs explicit filter; teachers use security rules)
        const weekday = this._weekdayStr(this.state.date);
        const scheduleDomain = [["weekday", "=", weekday]];
        if (session.is_admin || session.is_system) {
            const employees = await this.orm.searchRead(
                "hr.employee", [["user_id", "=", session.uid]], ["id"]
            );
            const teacherIds = employees.map(e => e.id);
            if (teacherIds.length) {
                scheduleDomain.push(["attendance_template_id.teacher_id", "in", teacherIds]);
            }
        }
        const schedules = await this.orm.searchRead(
            "ems.attendance_schedule",
            scheduleDomain,
            ["id", "name", "time_range", "attendance_template_id", "start_time"],
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

        this._autoSelect();
        this.state.loading = false;
    }

    async _loadLines(sessionId) {
        if (!sessionId) { this.state.lines = []; return; }
        const lines = await this.orm.searchRead(
            "ems.attendance_session_line",
            [["attendance_session_id", "=", sessionId]],
            ["id", "student_id", "status"],
            { order: "student_id asc" }
        );
        this.state.lines = lines;
        this.state.saving = {};
    }

    _autoSelect() {
        const sessions = this.filteredSessions;
        const planned = this.filteredPlanned;

        // Keep current selection if it's still visible after filtering
        const currentValid = this.state.selected && (
            sessions.some(s => `session_${s.id}` === this.state.selected) ||
            planned.some(s => `schedule_${s.id}` === this.state.selected)
        );
        if (currentValid) return;

        if (sessions.length) {
            this.state.selected = `session_${sessions[0].id}`;
            this._loadLines(sessions[0].id);
        } else if (planned.length) {
            this.state.selected = `schedule_${planned[0].id}`;
            this.state.lines = [];
        } else {
            this.state.selected = null;
            this.state.lines = [];
        }
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
        this.state.date = this._shiftDate(this.state.date, 1);
        await this._loadAll();
    }

    async onDateInput(ev) {
        if (!ev.target.value) return;
        this.state.date = ev.target.value;
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

    async onStatusClick(lineId, status) {
        if (this.state.saving[lineId]) return;
        this.state.saving[lineId] = true;
        try {
            await this.orm.write("ems.attendance_session_line", [lineId], { status });
            const line = this.state.lines.find(l => l.id === lineId);
            if (line) line.status = status;
        } finally {
            this.state.saving[lineId] = false;
        }
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
        } finally {
            this.state.loading = false;
        }
    }
}

registry.category("actions").add("ems_attendance_session_view", AttendanceSessionView);
