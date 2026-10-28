/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #460: a new student can't be saved without a Student ID (IDALU), nor (issue #640) without
// a birth date. The form marks both required while the record is new (rules that only apply going
// forward), and the student saves once they are filled in.
registry.category("web_tour.tours").add("ems_contact_new_student_requires_student_id", {
    url: "/odoo/action-ems.action_student_form/new",
    steps: () => [
        {
            content: "The Student ID is required on a new student",
            trigger: ".o_form_view .o_field_widget[name='student_id'].o_required_modifier",
        },
        {
            content: "So is the birth date (issue #640)",
            trigger: ".o_form_view .o_field_widget[name='birth_date'].o_required_modifier",
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
            trigger: ".o_form_view .o_field_widget[name='birth_date'] input",
            run: "edit 01/15/2010",
        },
        {
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            content: "Saved: an existing student no longer shows the fields as required",
            trigger: ".o_form_view .o_field_widget[name='student_id']:not(.o_required_modifier)",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='birth_date']:not(.o_required_modifier)",
        },
    ],
});
