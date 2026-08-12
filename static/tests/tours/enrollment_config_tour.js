/** @odoo-module **/

import { registry } from "@web/core/registry";

// "Enrollments" (action_enrollment_tree, ems.enrollment - the student x group x subject
// junction, Community > Configuration > Students) had zero coverage. Distinct from the
// well-tested action_ems_enrollments (sale.order, "Academic management > Enrollment >
// Enrollments") - different model, easy to conflate by name alone.
registry.category("web_tour.tours").add("ems_enrollment_config_crud", {
    test: true,
    url: "/odoo/action-ems.action_enrollment_tree",
    steps: () => [
        { trigger: ".o_list_view", content: "Enrollments list loaded" },
        { trigger: ".o_list_button_add", content: "Create a new enrollment", run: "click" },
        {
            trigger: ".o_form_view .o_field_widget[name='student_id'] input",
            content: "Search for the seeded student",
            run: "edit Enrollment Config Tour Student",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Enrollment Config Tour Student')",
            content: "Select the student",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='subject_id'] input",
            content: "Search for the seeded subject",
            run: "edit Enrollment Config Tour Subject",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Enrollment Config Tour Subject')",
            content: "Select the subject",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='group_id'] input",
            content: "Search for the seeded group",
            run: "edit EGCT1A",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('EGCT1A')",
            content: "Select the group",
            run: "click",
        },
        { trigger: ".o_form_button_save", content: "Save", run: "click" },
        { trigger: ".o_form_button_save:not(:visible)", content: "Save completed" },
    ],
});
