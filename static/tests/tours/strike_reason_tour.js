/** @odoo-module **/

import { registry } from "@web/core/registry";

// ems.strike.reason (Coexistence > Configuration > Strikes > Reasons): had zero browser
// coverage. A plain create-CRUD smoke test.
registry.category("web_tour.tours").add("ems_strike_reason_crud", {
    test: true,
    url: "/odoo/action-ems.action_strike_reason_list",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Strike reasons list loaded",
        },
        {
            trigger: ".o_list_button_add",
            content: "Create a new strike reason",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='name'] input",
            content: "Fill in the name",
            run: "edit Tour Strike Reason",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_breadcrumb:contains('Tour Strike Reason')",
            content: "The strike reason was created and saved",
        },
    ],
});
