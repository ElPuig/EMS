/** @odoo-module **/
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { usePrintAttendanceReport } from "./attendance_report_print";

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

// Single entry that opens the unified wizard; the user picks the report type (group / student /
// subject) inside the form via its 'report_type' selector.
class AttendanceReportCogMenu extends Component {
    static template = "cog_menu.AttendanceReportCogMenu";
    static components = { DropdownItem };
    static props = {};

    setup() {
        this.print = usePrintAttendanceReport();
    }

    onClickCogMenu() {
        this.print();
    }
}

cogMenuRegistry.add(
    "attendance-report-cog-menu",
    { Component: AttendanceReportCogMenu, groupNumber: 20, isDisplayed: isOnAttendanceReportsScreen },
    { sequence: 10 }
);
