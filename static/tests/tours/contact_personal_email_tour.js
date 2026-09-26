/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #514: a student's personal email can't be an address of the centre's own domain. Saving
// one surfaces the validation dialog; a real personal address then saves normally. The corporate
// domain is a fictitious one set by the Python side (school.example.com).
registry.category("web_tour.tours").add("ems_contact_personal_email_not_corporate", {
    url: "/odoo/action-ems.action_student_form/new",
    steps: () => [
        {
            trigger: ".o_form_view .o_field_widget[name='firstname'] input",
            run: "edit Corporate",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='lastname'] input",
            run: "edit Email Tour",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Student data')",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='student_id'] input",
            run: "edit TOUR514001",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='email'] input",
            run: "edit laia@school.example.com",
        },
        {
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            content: "The corporate address is rejected with a validation dialog",
            trigger: ".o_error_dialog:contains('school.example.com')",
        },
        {
            trigger: ".o_error_dialog .modal-footer .btn-primary",
            run: "click",
        },
        {
            trigger: "body:not(:has(.o_error_dialog)) .o_form_view .o_field_widget[name='email'] input",
            run: "edit laia@example.com",
        },
        {
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            content: "A personal address saves: the record is no longer new",
            trigger: ".o_form_view .o_form_saved",
        },
    ],
});
