/** @odoo-module **/

import { registry } from "@web/core/registry";
import { clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

// Issue #595: "Reset Google password" in the employee form's Actions dropdown, driven by a TAC
// member (the least-privileged role holding it), and the credentials PDF shown on the form: the
// previous one before the reset, the new one after it, in the Human Resources tab.
registry.category("web_tour.tours").add("ems_employee_google_password_reset", {
    test: true,
    steps: () => [
        {
            trigger: ".o_notebook .nav-link[name='hr_settings']",
            content: "Open the Human Resources tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='google_credentials_pdf']:contains('old_credentials.pdf')",
            content: "The current credentials PDF shows on the teacher's form",
        },
        ...clickAction("action_reset_google_password", "Reset the Google password"),
        {
            trigger: ".modal .modal-footer .btn-primary",
            content: "Confirm the reset",
            run: "click",
        },
        {
            trigger: ".o-mail-Message:contains('Google Workspace password reset')",
            content: "The reset is noted in the chatter",
        },
        {
            trigger: ".o_notebook .nav-link[name='hr_settings']",
            content: "Open the Human Resources tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='google_credentials_pdf']:contains('Credencials_Google_')",
            content: "The new credentials PDF replaced the old one",
        },
    ],
});
