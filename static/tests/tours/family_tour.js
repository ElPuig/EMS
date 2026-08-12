/** @odoo-module **/

import { registry } from "@web/core/registry";

// The "Families" filtered res.partner screen (Educational Community > Families) had zero
// browser coverage - a plain create-CRUD smoke test. EMS's own res.partner form (unlike
// native Odoo's single name field) splits it into separate firstname/lastname fields
// (partner_firstname convention, also used by the student/applicant import wizards).
registry.category("web_tour.tours").add("ems_family_crud", {
    test: true,
    url: "/odoo/action-ems.action_family_list",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Families list loaded",
        },
        {
            trigger: ".o_list_button_add",
            content: "Create a new family contact",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='firstname'] input",
            content: "Fill in the first name",
            run: "edit Tour",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='lastname'] input",
            content: "Fill in the last name",
            run: "edit Family Contact",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_form_button_save:not(:visible)",
            content: "Save completed",
        },
        {
            trigger: ".o_breadcrumb:contains('Tour Family Contact')",
            content: "The family contact was created and saved",
        },
    ],
});
