/** @odoo-module **/

import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("ems_workgroup_crud", {
    test: true,
    url: "/odoo/action-ems.action_workgroup_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Workgroups list view loaded",
        },
        {
            trigger: ".o_list_button_add",
            content: "Click New to create a workgroup",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='name'] input",
            content: "Fill in name",
            run: "edit Tour Test Workgroup",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save the new workgroup",
            run: "click",
        },
        {
            trigger: ".o_breadcrumb a",
            content: "Navigate back to the list",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='name']:contains('Tour Test Workgroup')",
            content: "New workgroup confirmed in list",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='name']:contains('Tour Test Workgroup')",
            content: "Open workgroup to edit",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='name'] input",
            content: "Edit the name",
            run: "edit Tour Test Workgroup Updated",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save the updated name",
            run: "click",
        },
        {
            trigger: ".o_breadcrumb a",
            content: "Back to list to verify edit",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='name']:contains('Tour Test Workgroup Updated')",
            content: "Updated name confirmed in list",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='name']:contains('Tour Test Workgroup Updated')",
            content: "Open workgroup to delete",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_cp_action_menus button",
            content: "Open action menu",
            run: "click",
        },
        {
            trigger: ".o_menu_item:contains('Delete')",
            content: "Click Delete",
            run: "click",
        },
        {
            trigger: ".modal-footer .btn-primary",
            content: "Confirm deletion",
            run: "click",
        },
        // Production only has one other workgroup — deleting the last one in the (now
        // two-record) alphabetical order lands Odoo on that adjacent record's form instead
        // of the list, unlike models with enough records that this is never the case.
        // Force a return to the list either way rather than assuming which state we're in.
        {
            trigger: ".o_list_view, .o_breadcrumb a",
            content: "Back in list after deletion (navigating there explicitly if Odoo landed on the one remaining record's form instead)",
            run: () => {
                document.querySelector(".o_breadcrumb a")?.click();
            },
        },
        {
            trigger: ".o_list_view",
            content: "Confirmed back in list",
        },
        {
            trigger: ".o_list_view:not(:has(.o_data_row td[name='name']:contains('Tour Test Workgroup Updated')))",
            content: "Workgroup deleted — no longer in list",
        },
    ],
});
