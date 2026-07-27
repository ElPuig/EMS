/** @odoo-module **/

import { registry } from "@web/core/registry";

// The 3 PDF report variants (by group / student / subject) are driven by a single unified wizard
// (ems.attendance_report_wizard) with a 'report_type' radio selector — the form's fields adapt to
// the chosen type. This tour switches through all 3 types on one open form (confirming each renders
// and its onchange-driven fields fill), exercises the shared opt-in Detail statuses / Include
// strikes controls + the inline size warning, and prints once at the end (printing returns a report
// download action, which closes the wizard dialog — so the single print comes last).
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

function pickReportType(label) {
    return {
        trigger: `.o_form_view .o_field_widget[name='report_type'] label:contains('${label}')`,
        content: `Switch report type to '${label}'`,
        run: "click",
    };
}

registry.category("web_tour.tours").add("ems_attendance_report_wizard", {
    test: true,
    url: "/odoo/action-ems.action_attendance_report_wizard",
    steps: () => [
        // --- By group (the default report_type) ---
        { trigger: ".o_form_view .o_field_widget[name='report_type']", content: "Unified report wizard loaded" },
        { trigger: ".o_form_view .o_field_widget[name='group_id']", content: "By-group selector shown by default" },
        ...selectMany2one("group_id", "Attendance Reports Tour Group"),
        {
            trigger: ".o_form_view .o_field_widget[name='tutor_ids'] .o_tag",
            content: "tutor_ids got auto-filled from the picked group",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='from_date'] input:not([value=''])",
            content: "from_date got auto-filled by the group's onchange",
        },

        // --- Switch to by student ---
        pickReportType("By student"),
        { trigger: ".o_form_view .o_field_widget[name='student_id']", content: "By-student selector now shown" },
        ...selectMany2one("student_id", "Attendance Reports Tour Student"),
        {
            trigger: ".o_form_view .o_field_widget[name='from_date'] input:not([value=''])",
            content: "from_date got auto-filled by the student's onchange",
        },

        // --- Switch to by subject (the richest variant: prefilled groups + the detail controls) ---
        pickReportType("By subject"),
        { trigger: ".o_form_view .o_field_widget[name='subject_id']", content: "By-subject selector now shown" },
        ...selectMany2one("subject_id", "Attendance Reports Tour Subject"),
        {
            trigger: ".o_form_view .o_field_widget[name='group_ids'] .o_tag:contains('Attendance Reports Tour Group')",
            content: "group_ids got pre-filled with every group teaching the subject",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='from_date'] input:not([value=''])",
            content: "from_date got auto-filled by the subject's onchange",
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
        // Adding a status beyond the absence-only default (e.g. 'Attended') must warn inline (not a
        // blocking dialog) that the per-dimension sections can grow large.
        ...selectMany2one("detail_status_ids", "Attended"),
        {
            trigger: ".o_form_view div[name='alert-detail-status-warning']:contains('The report may become very large')",
            content: "Picking a non-default status shows the inline size warning",
        },

        // Print closes the wizard dialog (returns a report download), so it comes last.
        { trigger: "button[name='print']", content: "Print the report", run: "click" },
        { trigger: "body:not(:has(.o_error_dialog))", content: "No client-side error after printing" },
    ],
});

// Self-service 'Attendance reports' screen (pivot/graph on ems.attendance_session_line, no list):
// entered through the 'Reports' menu's ir.actions.server (action_attendance_reports_open, role-
// based default domain) rather than the underlying act_window directly — that's the real entry
// point now. Confirms pivot is the default view, rows drill subject -> student (2 clicks on
// 'Expand all', per the decision not to add custom auto-expand JS), graph renders, and the unified
// PDF wizard is reachable from the Actions (cog) menu instead of a dedicated menu entry.
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
            trigger: ".o_attendance_report_cog_menu",
            content: "The single 'Print attendance report' shortcut is listed — click it",
            run: "click",
        },
        { trigger: ".o_form_view .o_field_widget[name='report_type']", content: "The unified report wizard opened" },
    ],
});
