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
            sessions: [],   // ems.attendance_session_header records for the date
            planned: [],    // ems.attendance_schedule records without a header for the date
            selected: null, // "session_<id>" or "schedule_<id>"
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

    // JS getDay() → 0=Sun; Python weekday() → 0=Mon. Convert:
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
            ["id", "time_range", "subject_id", "study_id", "attendance_schedule_id", "attendance_session_line_ids"],
            { order: "start_time asc" }
        );
        this.state.sessions = sessions;

        // 2. All schedules for this weekday.
        // For regular teachers, Odoo security rules already filter to their own schedules.
        // For admin users (security rules give full access), add an explicit teacher filter.
        const weekday = this._weekdayStr(this.state.date);
        const scheduleDomain = [["weekday", "=", weekday]];

        if (session.is_admin || session.is_system) {
            const employees = await this.orm.searchRead(
                "hr.employee",
                [["user_id", "=", session.uid]],
                ["id"]
            );
            const teacherIds = employees.map(e => e.id);
            if (teacherIds.length) {
                scheduleDomain.push(["attendance_template_id.teacher_id", "in", teacherIds]);
            }
        }

        const schedules = await this.orm.searchRead(
            "ems.attendance_schedule",
            scheduleDomain,
            ["id", "time_range", "attendance_template_id", "start_time"],
            { order: "start_time asc" }
        );

        // Keep only schedules that don't already have a header for this date
        const usedScheduleIds = new Set(
            sessions.filter(s => s.attendance_schedule_id).map(s => s.attendance_schedule_id[0])
        );
        this.state.planned = schedules.filter(s => !usedScheduleIds.has(s.id));

        // Auto-select first item
        const firstSession = sessions[0];
        const firstPlanned = this.state.planned[0];
        if (firstSession) {
            this.state.selected = `session_${firstSession.id}`;
            await this._loadLines(firstSession.id);
        } else if (firstPlanned) {
            this.state.selected = `schedule_${firstPlanned.id}`;
            this.state.lines = [];
        } else {
            this.state.selected = null;
            this.state.lines = [];
        }

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

    // ── Derived getters ───────────────────────────────────────────────────────

    get selectedSession() {
        if (!this.state.selected?.startsWith("session_")) return null;
        const id = parseInt(this.state.selected.split("_")[1]);
        return this.state.sessions.find(s => s.id === id) || null;
    }

    get selectedSchedule() {
        if (!this.state.selected?.startsWith("schedule_")) return null;
        const id = parseInt(this.state.selected.split("_")[1]);
        return this.state.planned.find(s => s.id === id) || null;
    }

    sessionLabel(s) {
        const subject = s.subject_id ? s.subject_id[1] : "—";
        return `${s.time_range}  ·  ${subject}`;
    }

    scheduleLabel(s) {
        const template = s.attendance_template_id ? s.attendance_template_id[1] : "—";
        return `${s.time_range}  ·  ${template}`;
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
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "ems.attendance_session_header",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
            context: {
                default_date: this.state.date,
                default_attendance_schedule_id: scheduleId,
                default_mode: "scheduled",
            },
        });
        await this._loadAll();
    }
}

registry.category("actions").add("ems_attendance_session_view", AttendanceSessionView);
