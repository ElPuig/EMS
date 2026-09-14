/** @odoo-module **/

import { registry } from "@web/core/registry";

// ems.authorization.template (Academic Management > Authorizations > Configuration >
// Authorization Forms): create a form, flip both of its routes, and open the send assistant
// from the form's own button - the way it failed when tested by hand.
registry.category("web_tour.tours").add("ems_authorization_template_crud", {
    test: true,
    url: "/odoo/action-ems.action_ems_authorization_template",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Authorization templates list loaded",
        },
        {
            trigger: ".o_list_button_add",
            content: "Create a new authorization template",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='name'] input",
            content: "Fill in the name",
            run: "edit Tour Authorization Template",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='legal_text'] .note-editable",
            content: "Fill in the required legal text",
            run: "editor Tour legal text",
        },
        {
            trigger: ".o_notebook .nav-link:contains('Data Fields')",
            content: "Open the Data Fields tab (field_ids, never rendered by any tour before)",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='field_ids']",
            content: "The (empty) fields list renders without crashing",
        },
        {
            // A form that does not apply to the enrollment never touches open enrollments, so
            // the two buttons acting on them have to disappear with the flag.
            trigger: ".o_form_view .o_field_widget[name='apply_on_enrollment'] input",
            content: "Stop applying it to the enrollment",
            run: "click",
        },
        {
            trigger: ".o_form_view:not(:has(button[name='action_apply_to_open_enrollments']))",
            content: "The enrollment-only buttons are gone",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='sendable_during_course'] input",
            content: "Make it sendable during the course",
            run: "click",
        },
        {
            // Regression guard: from here, active_ids carry this form's own id, which the
            // assistant used to read as a student and fail with "record does not exist" - an
            // error dialog logs a console error, which fails the tour.
            trigger: ".o_form_view button[name='action_send_to_students']",
            content: "Open the send assistant from the form itself (saves the form first)",
            run: "click",
        },
        {
            trigger: ".o_dialog .o_field_widget[name='template_ids']:contains('Tour Authorization Template')",
            content: "The assistant opened, preloaded with this form",
        },
        {
            trigger: ".o_dialog .modal-header .btn-close",
            content: "Close the assistant",
            run: "click",
        },
        {
            trigger: "body:not(:has(.o_dialog))",
            content: "Back on the form",
        },
        {
            trigger: ".o_breadcrumb:contains('Tour Authorization Template')",
            content: "The authorization template was saved",
        },
    ],
});
