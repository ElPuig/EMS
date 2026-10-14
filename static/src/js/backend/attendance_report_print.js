/** @odoo-module **/
import { useService } from "@web/core/utils/hooks";

// Opens the attendance PDF report wizard: the 'Attendance reports' screen's print button
// (views/attendance_report_analysis/, lazy-loaded with the pivot and graph views) and its ⚙ entry.
export function usePrintAttendanceReport() {
    const action = useService("action");
    return () => action.doAction("ems.action_attendance_report_wizard");
}
