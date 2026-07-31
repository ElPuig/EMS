/** @odoo-module **/

import { registry } from "@web/core/registry";

// ems.attendance_issue_tutor/_student/_status: the daily notification-tracking report
// (Attendances > Daily issues) had zero browser coverage. Every view here is fully read-only
// (create="False" edit="False" delete="False" throughout) - these records are only ever
// generated automatically (ems.attendance_session_line._update_notification()), never
// created by hand - so this tour is a pure render smoke test across both nested levels: the
// tutor-level report and, drilling into a student row, the session/status-level detail.
registry.category("web_tour.tours").add("ems_attendance_issue_drill_down", {
    test: true,
    url: "/odoo/action-ems.action_attendance_issue_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Daily issues list loaded",
        },
        {
            trigger: ".o_list_view .o_data_row td:contains('Attendance Issue Tour Tutor')",
            content: "Open the seeded tutor report",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='issue_date']",
            content: "Tutor report form loaded",
        },
        {
            trigger: ".o_field_widget[name='attendance_issue_student_ids'] .o_data_row td:contains('Attendance Issue Tour Student')",
            content: "Drill into the seeded student row",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='attendance_issue_status_ids'] .o_data_row td:contains('Test Subject (Attendance Issue Tour)')",
            content: "The student's session/status detail renders without crashing",
        },
    ],
});
