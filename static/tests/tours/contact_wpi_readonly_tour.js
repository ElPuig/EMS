/** @odoo-module **/

import { registry } from "@web/core/registry";

// Regression (found 2026-09-06, alongside issue #395): 'wpi_enrolled' was missing
// 'read_only_user' from its readonly condition - is_tutor_readonly alone is False for a
// teacher who isn't THIS student's own tutor, so the field looked editable for a teacher/tutor
// viewing any OTHER student, not just their own tutorands, unlike every sibling field on the
// same tab (see views/community/contact/form.xml).
registry.category("web_tour.tours").add("ems_contact_wpi_readonly_for_non_tutorand", {
    test: true,
    url: "/odoo/action-ems.action_student_kanban",
    steps: () => [
        {
            trigger: ".o_control_panel",
            content: "Educational Community loaded",
        },
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to list view",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('0001 Group Change Tour Non-Tutorand')",
            content: "Open a student this teacher/tutor does NOT tutor",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Studies')",
            content: "Open the Studies tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='wpi_enrolled'].o_readonly_modifier",
            content: "REGRESSION CHECK: wpi_enrolled is read-only for a non-tutorand student",
        },
    ],
});
