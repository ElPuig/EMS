/** @odoo-module **/
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const cogMenuRegistry = registry.category("cogMenu");

let _attendanceReportsActionId = null;

// Scoped to the 'Reports' (Attendance reports pivot/graph) screen only, matched the same way as
// ImportGedacCogMenu (import_gedac_cog_menu.js): by resolving the menu's own actionID once and
// comparing it against the currently open action.
function isOnAttendanceReportsScreen(env) {
    const { actionType, actionId } = env.config;
    if (actionType !== "ir.actions.act_window" || !actionId) {
        return false;
    }
    if (_attendanceReportsActionId === null) {
        try {
            const menu = env.services.menu.getAll().find((m) => m.xmlid === "ems.menu_attendance_reports");
            _attendanceReportsActionId = menu ? menu.actionID : false;
        } catch {
            _attendanceReportsActionId = false;
        }
    }
    return actionId === _attendanceReportsActionId;
}

class AttendanceReportGroupCogMenu extends Component {
    static template = "cog_menu.AttendanceReportGroupCogMenu";
    static components = { DropdownItem };
    static props = {};

    setup() {
        this.action = useService("action");
    }

    onClickCogMenu() {
        this.action.doAction("ems.action_attendance_report_group_wizard");
    }
}

class AttendanceReportStudentCogMenu extends Component {
    static template = "cog_menu.AttendanceReportStudentCogMenu";
    static components = { DropdownItem };
    static props = {};

    setup() {
        this.action = useService("action");
    }

    onClickCogMenu() {
        this.action.doAction("ems.action_attendance_report_student_wizard");
    }
}

class AttendanceReportSubjectCogMenu extends Component {
    static template = "cog_menu.AttendanceReportSubjectCogMenu";
    static components = { DropdownItem };
    static props = {};

    setup() {
        this.action = useService("action");
    }

    onClickCogMenu() {
        this.action.doAction("ems.action_attendance_report_subject_wizard");
    }
}

cogMenuRegistry.add(
    "attendance-report-group-cog-menu",
    { Component: AttendanceReportGroupCogMenu, groupNumber: 20, isDisplayed: isOnAttendanceReportsScreen },
    { sequence: 10 }
);
cogMenuRegistry.add(
    "attendance-report-student-cog-menu",
    { Component: AttendanceReportStudentCogMenu, groupNumber: 20, isDisplayed: isOnAttendanceReportsScreen },
    { sequence: 11 }
);
cogMenuRegistry.add(
    "attendance-report-subject-cog-menu",
    { Component: AttendanceReportSubjectCogMenu, groupNumber: 20, isDisplayed: isOnAttendanceReportsScreen },
    { sequence: 12 }
);
