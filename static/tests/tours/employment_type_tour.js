/** @odoo-module **/

import { registry } from "@web/core/registry";

// hr.contract.type (Employment types): plain native Odoo model, no EMS-specific view. Its
// list is editable="bottom", so "New" creates an inline row rather than navigating to a form
// page - had zero browser coverage. A plain create-CRUD smoke test.
registry.category("web_tour.tours").add("ems_employment_type_crud", {
    test: true,
    url: "/odoo/action-ems.action_employmenttypes_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Employment types list loaded",
        },
        {
            trigger: ".o_list_button_add",
            content: "Create a new employment type (inline row)",
            run: "click",
        },
        {
            trigger: ".o_selected_row .o_field_widget[name='name'] input",
            content: "Fill in the name",
            run: "edit Tour Employment Type",
        },
        {
            trigger: ".o_list_button_save",
            content: "Save the inline row",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row td:contains('Tour Employment Type')",
            content: "The employment type was created and saved",
        },
    ],
});
