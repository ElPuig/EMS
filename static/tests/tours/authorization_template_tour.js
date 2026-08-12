/** @odoo-module **/

import { registry } from "@web/core/registry";

// ems.authorization.template (Academic Management > Enrollment Configuration > Authorization
// Forms): had zero browser coverage, including its own widget="html" legal_text field. A
// plain create-CRUD smoke test - both name and legal_text are required.
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
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_form_button_save:not(:visible)",
            content: "Save completed",
        },
        {
            trigger: ".o_breadcrumb:contains('Tour Authorization Template')",
            content: "The authorization template was created and saved",
        },
    ],
});
