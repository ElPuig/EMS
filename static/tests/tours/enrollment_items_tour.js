/** @odoo-module **/

import { registry } from "@web/core/registry";

// product.template's "Enrollment Item" screen (Academic Management > Enrollment Configuration):
// a heavily xpath-customized product form (EMS study/level linkage, generic-fee toggles) had
// zero browser coverage. A plain create-CRUD smoke test - default context starts a new item as
// is_generic=True, which makes default_code required.
registry.category("web_tour.tours").add("ems_enrollment_item_crud", {
    test: true,
    url: "/odoo/action-ems.action_ems_enrollment_items",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Enrollment items list loaded",
        },
        {
            trigger: ".o_list_button_add",
            content: "Create a new enrollment item",
            run: "click",
        },
        {
            // product.template's native name field is widget="text" (a <textarea>), same
            // pattern as hr.job's - not a plain Char <input>.
            trigger: ".o_form_view .o_field_widget[name='name'] textarea",
            content: "Fill in the name",
            run: "edit Tour Enrollment Item",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='default_code'] input",
            content: "Fill in the internal reference (required while is_generic)",
            run: "edit TOUR-ITEM",
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
            trigger: ".o_breadcrumb:contains('Tour Enrollment Item')",
            content: "The enrollment item was created and saved",
        },
    ],
});
