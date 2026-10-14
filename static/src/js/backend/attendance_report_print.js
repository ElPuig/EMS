/** @odoo-module **/
import { useEnv } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

// The search facets that prefill the PDF wizard (see ems.attendance_report_wizard.default_get):
// a student, a group and a subject picked in the search bar (or set by the student form's
// 'Attendance' button). A facet holding several values, or free text, is ambiguous and ignored.
const PREFILLED_FIELDS = ["student_id", "student_group_id", "subject_id"];

function attendanceReportDefaults(searchModel) {
    const values = {};
    for (const { searchItemId, autocompleteValue } of searchModel?.query || []) {
        const fieldName = searchModel.searchItems[searchItemId]?.fieldName;
        if (!PREFILLED_FIELDS.includes(fieldName) || !autocompleteValue) {
            continue;
        }
        const { operator, value } = autocompleteValue;
        const recordId = operator === "=" && Number.isInteger(value) ? value : false;
        values[fieldName] = fieldName in values ? false : recordId;
    }
    const context = {};
    for (const [fieldName, recordId] of Object.entries(values)) {
        if (recordId) {
            context[`ems_report_${fieldName}`] = recordId;
        }
    }
    return context;
}

// Opens the attendance PDF report wizard, prefilled from the active search facets: the 'Attendance
// reports' screen's print button (views/attendance_report_analysis/, lazy-loaded with the pivot and
// graph views) and its ⚙ entry.
export function usePrintAttendanceReport() {
    const action = useService("action");
    const env = useEnv();
    return () => action.doAction("ems.action_attendance_report_wizard", {
        additionalContext: attendanceReportDefaults(env.searchModel),
    });
}
