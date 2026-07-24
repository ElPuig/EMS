/** @odoo-module **/
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const cogMenuRegistry = registry.category("cogMenu");

// Scoped to the pivot/graph views of ems.attendance_session_line only — the only screen using
// that model, so no need for the extra actionID/menu-xmlid indirection ImportGedacCogMenu
// (import_gedac_cog_menu.js) uses to disambiguate a model shared by several menus. Matching by
// actionId isn't reliable here anyway: the 'Reports' menu opens through an ir.actions.server
// (action_attendance_reports_open, for role-based default domain scoping) that redirects to this
// action, so env.config.actionId at render time is the act_window's id, not the menu's own
// configured action id.
function isOnAttendanceReportsScreen(env) {
    const { actionType, viewType } = env.config;
    if (actionType !== "ir.actions.act_window" || !["pivot", "graph"].includes(viewType)) {
        return false;
    }
    return env.searchModel?.resModel === "ems.attendance_session_line";
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
