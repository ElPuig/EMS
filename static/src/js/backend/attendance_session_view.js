/** @odoo-module **/

import { Component, useState, onWillStart, useRef } from "@odoo/owl";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";
import { _t } from "@web/core/l10n/translation";

const { DateTime } = luxon;
import { DateTimePicker } from "@web/core/datetime/datetime_picker";
import { useDateTimePicker } from "@web/core/datetime/datetime_hook";
import { usePopover } from "@web/core/popover/popover_hook";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";

class EmsDatePickerPopover extends Component {
    static components = { DateTimePicker };
    static props = { close: Function, pickerProps: Object };
    static template = "ems.EmsDatePickerPopover";

    setup() {
        useHotkey("escape", () => this.props.close());
    }

    get todayLabel() { return _t("Today"); }

    goToday() {
        this.props.pickerProps.onSelect?.(DateTime.now(), "date");
        this.props.close();
    }
}

class EmsDateInput extends Component {
    static props = {
        value:    Object,
        onApply:  Function,
        disabled: { type: Boolean, optional: true },
    };
    static template = "ems.EmsDateInput";

    setup() {
        const self = this;
        useDateTimePicker({
            createPopover: (_, options) => usePopover(EmsDatePickerPopover, options),
            get pickerProps() {
                return { type: "date", value: self.props.value, maxDate: DateTime.now() };
            },
            onApply: (value) => self.props.onApply(value),
        });
    }
}


class AttendanceSessionView extends Component {
    static template = "ems.AttendanceSessionView";
    static props = ["*"];
    static components = { EmsDateInput };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.statuses = [];   // populated in onWillStart from model fields_get

        this.notesDialog   = useRef("notesDialog");
        this.notesTextarea = useRef("notesTextarea");
        this._lastnameMap  = {};

        this.strikeDialog        = useRef("strikeDialog");
        this.strikeReasonSelect  = useRef("strikeReasonSelect");
        this.strikeNotesTextarea = useRef("strikeNotesTextarea");
        this.strikeReasons = [];   // populated in onWillStart from ems.strike.reason

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
            editingStrikeStudentId: null,
            editingStrikeStudentName: "",
            sortField: 'lastname',  // 'lastname' | 'name'
            sortDir:   'asc',       // 'asc' | 'desc'
            viewMode: 'current',    // 'current' | 'manual' | 'guard'
            showContinuationBanner: false,
            multipleCurrentSessions: false,
        });

        onWillStart(async () => {
            await Promise.all([this._loadStatuses(), this._loadStrikeReasons()]);
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

    async _loadStrikeReasons() {
        this.strikeReasons = await this.orm.searchRead(
            "ems.strike.reason", [["active", "=", true]], ["id", "name"]
        );
    }

    async _loadAll() {
        this.state.loading = true;
        try {
            const now = this._nowAsFloat();
            if (this.state.viewMode === 'guard') {
                await this._loadAllGuard(now);
            } else {
                await this._loadAllNormal(now);
            }
            await this._autoSelect(now);
        } finally {
            this.state.loading = false;
        }
    }

    async _loadAllNormal(now) {
        const { sessions, planned } = await this.orm.call(
            "ems.attendance_session_header", "get_normal_sessions_and_planned", [this.state.date]
        );

        let filteredSessions = sessions;
        let filteredPlanned  = planned;

        if (this.state.viewMode === 'current') {
            filteredSessions = filteredSessions.filter(s => this._isCurrentSlot(s, now));
            filteredPlanned  = filteredPlanned.filter(s => this._isCurrentSlot(s, now));
        }

        this.state.sessions = filteredSessions;
        this.state.planned  = filteredPlanned;
        this.state.multipleCurrentSessions =
            this.state.viewMode === 'current' &&
            (filteredSessions.length + filteredPlanned.length) > 1;

        const allGroups = new Set([
            ...filteredSessions.map(s => this._groupFromScheduleName(
                s.attendance_schedule_id ? s.attendance_schedule_id[1] : '')),
            ...filteredPlanned.map(s => this._groupFromScheduleName(s.name || '')),
        ]);
        allGroups.delete('');
        this.state.groups = [...allGroups].sort();
        this.state.selectedGroup = null;
    }

    async _loadAllGuard(now) {
        this.state.date = this._todayStr();
        const [allSessions, allPlanned] = await Promise.all([
            this.orm.call("ems.attendance_session_header", "get_guard_sessions", [this.state.date]),
            this.orm.call("ems.attendance_session_header", "get_guard_planned",  [this.state.date]),
        ]);
        const sessions = allSessions.filter(s => this._isCurrentSlot(s, now));
        const planned  = allPlanned.filter(s => this._isCurrentSlot(s, now));
        this.state.sessions = sessions;
        this.state.planned  = planned;

        const allGroups = new Set([
            ...sessions.map(s => this._groupFromScheduleName(
                s.attendance_schedule_id ? s.attendance_schedule_id[1] : '')),
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
            ["id", "student_id", "status", "notes", "attendance_justification_id", "attendance_prevision_id"],
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

    _isCurrentSlot(s, now) {
        return s.start_time <= now && now < s.end_time;
    }

    _parseSelectedId() {
        return parseInt(this.state.selected.split("_")[1]);
    }

    async _writeSessionLine(lineId, values) {
        if (this.state.viewMode === 'guard') {
            await this.orm.call(
                "ems.attendance_session_header", "write_guard_session_line", [lineId, values]
            );
        } else {
            await this.orm.write("ems.attendance_session_line", [lineId], values);
        }
    }

    async _autoSelect(now) {
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
            bestSession = sessions.find(s => this._isCurrentSlot(s, now)) || null;
            if (!bestSession) {
                bestSchedule = planned.find(s => this._isCurrentSlot(s, now)) || null;
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

    get dateValue() { return DateTime.fromISO(this.state.date); }

    async onDateApply(value) {
        const today = this._todayStr();
        const str = (value ? value.toFormat("yyyy-MM-dd") : null) || today;
        this.state.date = str > today ? today : str;
        await this._loadAll();
    }

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
            addStrike:            _t("Issue a strike"),
            strikeNotesPlaceholder: _t("Details (optional)..."),
            send:                 _t("Send"),
            lastnameAZ:        _t("Lastname A→Z"),
            lastnameZA:        _t("Lastname Z→A"),
            nameAZ:            _t("Name A→Z"),
            nameZA:            _t("Name Z→A"),
            viewModeCurrent:        _t("Current session"),
            viewModeManual:         _t("Manual"),
            viewModeGuard:          _t("Guard"),
            continuationBanner:     _t("A previous session for the same subject has been detected for today, so assistance data has been copied from the previous one. You can modify any of those as you please."),
            multipleSessionsWarning: _t("More than one session is scheduled for the current time slot. Please select one manually or switch to 'Manual' mode."),
            justifiedTitle:          _t("Justified absence — status and notes are locked."),
            deleteSession:          _t("Delete session"),
            deleteSessionConfirm:   _t("Delete this session? This action cannot be undone."),
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
        return this.filteredSessions.find(s => s.id === this._parseSelectedId()) || null;
    }

    get selectedSchedule() {
        if (!this.state.selected?.startsWith("schedule_")) return null;
        return this.filteredPlanned.find(s => s.id === this._parseSelectedId()) || null;
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



    onGroupChange(ev) {
        this.state.selectedGroup = ev.target.value || null;
        this._autoSelect();
    }

    async onSelectorChange(ev) {
        this.state.selected = ev.target.value;
        this.state.showContinuationBanner = false;
        if (this.selectedSession) {
            await this._loadLines(this.selectedSession.id);
        } else {
            this.state.lines = [];
        }
    }

    async onViewModeChange(ev) {
        this.state.viewMode = ev.target.value;
        if (this.state.viewMode !== 'manual') {
            this.state.date = this._todayStr();
        }
        await this._loadAll();
    }

    async onStatusClick(lineId, status) {
        if (this.state.saving[lineId]) return;
        this.state.saving[lineId] = true;
        try {
            await this._writeSessionLine(lineId, { status });
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
        const notes  = this.notesTextarea.el.value.trim();
        await this._writeSessionLine(lineId, { notes: notes || false });
        const line = this.state.lines.find(l => l.id === lineId);
        if (line) line.notes = notes || false;
        this.notesDialog.el.close();
        this.state.editingLineId = null;
    }

    onStrikeClick(studentId, studentName) {
        this.state.editingStrikeStudentId = studentId;
        this.state.editingStrikeStudentName = studentName;
        this.strikeReasonSelect.el.value = this.strikeReasons.length ? this.strikeReasons[0].id : "";
        this.strikeNotesTextarea.el.value = "";
        this.strikeDialog.el.showModal();
    }

    onStrikeCancel() {
        this.strikeDialog.el.close();
        this.state.editingStrikeStudentId = null;
    }

    async onStrikeSend() {
        const studentId = this.state.editingStrikeStudentId;
        const reasonId  = parseInt(this.strikeReasonSelect.el.value);
        const notes     = this.strikeNotesTextarea.el.value.trim();
        await this.orm.create("ems.strike", [{
            student_id: studentId,
            reason_id: reasonId,
            notes: notes || false,
        }]);
        this.strikeDialog.el.close();
        this.state.editingStrikeStudentId = null;
    }

    onDeleteSession() {
        if (!this.selectedSession) return;
        const sessionId = this.selectedSession.id;
        this.dialog.add(ConfirmationDialog, {
            body: this.strings.deleteSessionConfirm,
            confirm: async () => {
                this.state.loading = true;
                try {
                    await this.orm.unlink("ems.attendance_session_header", [sessionId]);
                    this.state.selected = null;
                    await this._loadAll();
                } finally {
                    this.state.loading = false;
                }
            },
        });
    }

    async onStartSession(scheduleId) {
        this.state.loading = true;
        try {
            const { id: newId, is_continuation } = await this.orm.call(
                "ems.attendance_session_header", "create_scheduled_session",
                [this.state.date, scheduleId]
            );
            await this._loadAll();
            this.state.selected = "session_" + newId;
            await this._loadLines(newId);
            this.state.showContinuationBanner = is_continuation;
        } finally {
            this.state.loading = false;
        }
    }

    dismissContinuationBanner() {
        this.state.showContinuationBanner = false;
    }
}

registry.category("actions").add("ems_attendance_session_view", AttendanceSessionView);
