/** @odoo-module **/

import { registry } from "@web/core/registry";

// Smoke-tests ems.attendance_template's color widget on its own list+form
// (ems.action_attendance_template_tree). Unlike ems.role/hr.department, this model has no
// secondary view and is never embedded as tags/badges in another model's view, so list+form is
// the full picture here. Opens a new (unsaved) record rather than relying on an existing row,
// since attendance_template records are never seeded by a data file (only created at runtime by
// schedule sync) - a fresh install has none. See docs/en/developers/shared/color_widget.md.
registry.category("web_tour.tours").add("ems_attendance_template_color_smoke", {
    test: true,
    url: "/odoo/action-ems.action_attendance_template_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Attendance templates list view loaded",
        },
        {
            trigger: ".o_list_button_add",
            content: "Click New",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='color'] .o_field_color",
            content: "Color swatch rendered on the new record's form",
        },
    ],
});
