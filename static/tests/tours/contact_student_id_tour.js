/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #460: a new student can't be saved without a Student ID (IDALU). The "Student data" tab
// marks the field required while the record is new (matching the server rule, which only
// applies going forward), and the student saves once it is filled in.
registry.category("web_tour.tours").add("ems_contact_new_student_requires_student_id", {
    url: "/odoo/action-ems.action_student_form/new",
    steps: () => [
        {
            content: "Open the Student data tab of the new student",
            trigger: ".o_form_view .o_notebook .nav-link:contains('Student data')",
            run: "click",
        },
        {
            content: "The Student ID is required on a new student",
            trigger: ".o_form_view .o_field_widget[name='student_id'].o_required_modifier",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='firstname'] input",
            run: "edit IDALU",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='lastname'] input",
            run: "edit Tour Student",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='student_id'] input",
            run: "edit TOUR460001",
        },
        {
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            content: "Saved: an existing student no longer shows the field as required",
            trigger: ".o_form_view .o_field_widget[name='student_id']:not(.o_required_modifier)",
        },
    ],
});
