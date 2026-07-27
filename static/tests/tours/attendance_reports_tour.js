/** @odoo-module **/

import { registry } from "@web/core/registry";

// Attendance report wizards (group/student/subject): after their allowed_*_ids filters and
// print() were ported from raw SQL to ORM, confirm the OWL forms still render and clicking
// 'Print' doesn't crash. All 3 were later simplified to drop the level -> study -> group cascade:
// group/student down to a single group_id/student_id pick; subject down to a single subject_id
// pick that pre-fills a removable group_ids multi-select (every group teaching that subject) and
// a read-only tutor_ids multi-select — all scoped server-side by allowed_*_ids.
function selectMany2one(fieldName, searchText) {
    return [
        {
            trigger: `.o_form_view .o_field_widget[name='${fieldName}'] input`,
            content: `Search '${searchText}' on ${fieldName}`,
            run: `edit ${searchText}`,
        },
        {
            trigger: `.o-autocomplete--dropdown-item:contains('${searchText}')`,
            content: `Select '${searchText}'`,
            run: "click",
        },
    ];
}

registry.category("web_tour.tours").add("ems_attendance_report_group_wizard", {
    test: true,
    url: "/odoo/action-ems.action_attendance_report_group_wizard",
    steps: () => [
        { trigger: ".o_form_view .o_field_widget[name='group_id']", content: "Group report wizard loaded" },
        ...selectMany2one("group_id", "Attendance Reports Tour Group"),
        {
            trigger: ".o_form_view .o_field_widget[name='tutor_id']:not(:empty)",
            content: "tutor_id got auto-filled by the group's own related field",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='from_date'] input:not([value=''])",
            content: "from_date got auto-filled by the group's own onchange",
        },
        { trigger: "button[name='print']", content: "Print the group report", run: "click" },
        { trigger: "body:not(:has(.o_error_dialog))", content: "No client-side error after printing" },
    ],
});

registry.category("web_tour.tours").add("ems_attendance_report_subject_wizard", {
    test: true,
    url: "/odoo/action-ems.action_attendance_report_subject_wizard",
    steps: () => [
        { trigger: ".o_form_view .o_field_widget[name='subject_id']", content: "Subject report wizard loaded" },
        ...selectMany2one("subject_id", "Attendance Reports Tour Subject"),
        {
            trigger: ".o_form_view .o_field_widget[name='group_ids'] .o_tag:contains('Attendance Reports Tour Group')",
            content: "group_ids got pre-filled with every group teaching the subject",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='tutor_ids'] .o_tag",
            content: "tutor_ids got auto-filled with the pre-filled groups' tutors",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='from_date'] input:not([value=''])",
            content: "from_date got auto-filled by the subject's own onchange",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='detail_status_ids'] .o_tag:contains('Miss')",
            content: "detail_status_ids defaults to absence-category statuses only",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='include_strikes'] input:checked",
            content: "include_strikes defaults to enabled",
        },
        {
            trigger: ".o_form_view:not(:has(div[name='alert-detail-status-warning']))",
            content: "The size warning banner is absent while the selection stays within the default",
        },
        // Adding a status beyond the absence-only default (e.g. 'Attended') must warn inline (not
        // a blocking dialog) that the per-student sections can grow large — this is the opt-in
        // safety net from the report-scale fix, not just a cosmetic field.
        ...selectMany2one("detail_status_ids", "Attended"),
        {
            trigger: ".o_form_view div[name='alert-detail-status-warning']:contains('The report may become very large')",
            content: "Picking a non-default status shows the inline size warning",
        },
        { trigger: "button[name='print']", content: "Print the subject report", run: "click" },
        { trigger: "body:not(:has(.o_error_dialog))", content: "No client-side error after printing" },
    ],
});

registry.category("web_tour.tours").add("ems_attendance_report_student_wizard", {
    test: true,
    url: "/odoo/action-ems.action_attendance_report_student_wizard",
    steps: () => [
        { trigger: ".o_form_view .o_field_widget[name='student_id']", content: "Student report wizard loaded" },
        ...selectMany2one("student_id", "Attendance Reports Tour Student"),
        {
            trigger: ".o_form_view .o_field_widget[name='tutor_id']:not(:empty)",
            content: "tutor_id got auto-filled by the student's own related field",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='from_date'] input:not([value=''])",
            content: "from_date got auto-filled by the student's own onchange",
        },
        { trigger: "button[name='print']", content: "Print the student report", run: "click" },
        { trigger: "body:not(:has(.o_error_dialog))", content: "No client-side error after printing" },
    ],
});

// Self-service 'Attendance reports' screen (pivot/graph on ems.attendance_session_line, no list):
// entered through the 'Reports' menu's ir.actions.server (action_attendance_reports_open, role-
// based default domain) rather than the underlying act_window directly — that's the real entry
// point now. Confirms pivot is the default view, rows drill subject -> student (2 clicks on
// 'Expand all', per the decision not to add custom auto-expand JS), graph renders, and the 3 PDF
// wizards are reachable from the Actions (cog) menu instead of a dedicated menu entry.
registry.category("web_tour.tours").add("ems_attendance_report_analysis", {
    test: true,
    url: "/odoo/action-ems.action_attendance_reports_open",
    steps: () => [
        { trigger: ".o_pivot_view .o_pivot_cell_value", content: "Pivot renders by default with at least one value cell" },
        { trigger: ".o_pivot_flip_button, .o_pivot_expand_button", content: "Pivot toolbar loaded" },
        { trigger: ".o_pivot_expand_button", content: "Expand all: Total -> subject", run: "click" },
        {
            trigger: ".o_pivot_view :contains('Attendance Reports Tour Subject')",
            content: "Subject row appears",
        },
        { trigger: ".o_pivot_expand_button", content: "Expand all again: subject -> student", run: "click" },
        {
            trigger: ".o_pivot_view :contains('Attendance Reports Tour Student')",
            content: "Nested student row appears under the subject",
        },
        { trigger: ".o_switch_view.o_graph", content: "Switch to graph", run: "click" },
        { trigger: ".o_graph_renderer canvas", content: "Graph renders a chart (default measure: absence rate)" },
        { trigger: ".btn:contains('Measures')", content: "Open the Measures dropdown", run: "click" },
        {
            trigger: ".o_menu_item:contains('Strike count')",
            content: "'Strike count' is offered as an alternative measure — switch to it",
            run: "click",
        },
        { trigger: ".o_graph_renderer canvas", content: "Graph still renders after switching measure" },
        { trigger: ".o_cp_action_menus button:has(.fa-cog)", content: "Open the Actions cog menu", run: "click" },
        {
            trigger: ".o_attendance_report_group_cog_menu",
            content: "The 'Attendance report (by group)' shortcut is listed — click it",
            run: "click",
        },
        { trigger: ".o_form_view .o_field_widget[name='group_id']", content: "The group report wizard opened" },
    ],
});
