/** @odoo-module **/

import { registry } from "@web/core/registry";

// Smoke-tests ems.attendance_template's color widget on its own list+form
// (ems.action_attendance_template_tree). Unlike ems.role/hr.department, this model has no
// secondary view and is never embedded as tags/badges in another model's view, so list+form is
// the full picture here. Opens an EXISTING record (the Python test's own setUpClass fixture,
// created via sudo() exactly like the calendar-driven sync pipeline does internally) rather than
// creating one through the UI - the "New" button was removed 2026-08-11 (see
// plans/calendar_driven_attendance_templates.md, point 3): a template only ever comes from that
// pipeline now, never a direct admin/teacher create. See docs/en/developers/shared/color_widget.md.
registry.category("web_tour.tours").add("ems_attendance_template_color_smoke", {
    test: true,
    url: "/odoo/action-ems.action_attendance_template_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Attendance templates list view loaded",
        },
        {
            trigger: ".o_searchview_input",
            content: "Search for the fixture template by teacher (the search view's default "
                + "field) - this dev database has hundreds of real templates, so the fixture row "
                + "isn't necessarily on the list's first page",
            run: "edit Attendance Template Color Tour Teacher",
        },
        {
            trigger: ".o_searchview_input",
            content: "Confirm the search",
            run: "press Enter",
        },
        {
            trigger: ".o_data_row .o_field_widget[name='color'] .o_field_color",
            content: "Color swatch rendered in the list view",
        },
        {
            trigger: ".o_data_row td:contains('Test Subject (Attendance Template Color Tour)')",
            content: "Open the fixture record",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='color'] .o_field_color",
            content: "Color swatch rendered on the record's own form",
        },
    ],
});
