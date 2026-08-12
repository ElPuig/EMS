/** @odoo-module **/

import { registry } from "@web/core/registry";

// ems.attendance_template (the weekly recurring class schedule setup - Community >
// Configuration > Teachers > ... ): only ever had a shallow color-widget smoke test
// (attendance_template_color_tour.js) before this, never a real end-to-end view of a real
// record's own embedded "Sessions" tab (ems.attendance_schedule lines) and its "Students" dialog.
//
// Does NOT create a template through the UI - the "New" button was removed 2026-08-11 (see
// plans/calendar_driven_attendance_templates.md, point 3): a template only ever comes from the
// calendar-driven sync pipeline now, never a direct admin/teacher create. This tour instead opens
// a template the Python test's own setUpClass already created (via sudo(), mirroring exactly
// what that pipeline does internally) - the only way one can exist - and verifies VIEWING it
// still works end to end, including the schedule line's own "Students" dialog.
registry.category("web_tour.tours").add("ems_attendance_template_view_tour", {
    test: true,
    url: "/odoo/action-ems.action_attendance_template_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Attendance templates list loaded",
        },
        {
            trigger: ".o_list_view:not(:has(.o_list_button_add))",
            content: "The 'New' button is genuinely absent - creation is calendar-driven only now",
        },
        {
            trigger: ".o_searchview_input",
            content: "Search for the fixture template by teacher (the search view's default field) "
                + "- this dev database has hundreds of real templates, so the fixture row isn't "
                + "necessarily on the list's first page",
            run: "edit Attendance Template Tour Teacher",
        },
        {
            trigger: ".o_searchview_input",
            content: "Confirm the search",
            run: "press Enter",
        },
        {
            trigger: ".o_data_row td:contains('Test Subject (Attendance Template Tour)')",
            content: "Open the fixture template created via sudo() (mirrors the sync pipeline)",
            run: "click",
        },
        {
            trigger: ".o_breadcrumb:contains('Test Subject (Attendance Template Tour)')",
            content: "The record's own form loaded (breadcrumb reflects its display_name)",
        },
        {
            trigger: ".o_field_widget[name='attendance_schedule_ids'] .o_data_row",
            content: "The fixture's own schedule line renders in the Sessions list",
        },
        {
            trigger: ".o_field_widget[name='attendance_schedule_ids'] .o_data_row button[name='action_open_form']",
            content: "Open the schedule line's own form (student_ids lives here, not the "
                + "template - see plans/calendar_driven_attendance_templates.md, point 1)",
            run: "click",
        },
        {
            trigger: ".modal .o_notebook .nav-link:contains('Students')",
            content: "Open the Students tab on the schedule line's dialog",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='student_ids']",
            content: "The (empty) students list renders without crashing",
        },
        {
            trigger: ".modal-header .btn-close",
            content: "Close the dialog - nothing left to verify",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal)) .o_form_view",
            content: "Back on the template form, dialog closed cleanly",
        },
    ],
});
