/** @odoo-module **/

import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("ems_non_teaching_type_crud", {
    test: true,
    url: "/odoo/action-ems.action_non_teaching_type_list",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Non-teaching types list view loaded",
        },
        {
            trigger: ".o_list_button_add",
            content: "Click New",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='code'] input",
            content: "Fill in code",
            run: "edit TOURNTT",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='name'] input",
            content: "Fill in name",
            run: "edit Tour Test Non-Teaching Type",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_breadcrumb a",
            content: "Navigate back to the list",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='name']:contains('Tour Test Non-Teaching Type')",
            content: "New record confirmed in list",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='name']:contains('Tour Test Non-Teaching Type')",
            content: "Open to edit",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='is_break'] input",
            content: "Toggle is_break",
            run: "click",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save the edit",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='is_break'] input:checked",
            content: "is_break confirmed checked after save",
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
        // Deleting can land Odoo on an adjacent record's form instead of the list (same
        // observed behaviour as workgroup_tour.js) — force a return to the list either way.
        {
            trigger: ".o_list_view, .o_breadcrumb a",
            content: "Back in list after deletion (navigating there explicitly if needed)",
            run: () => {
                document.querySelector(".o_breadcrumb a")?.click();
            },
        },
        {
            trigger: ".o_list_view",
            content: "Confirmed back in list",
        },
        {
            trigger: ".o_list_view:not(:has(.o_data_row td[name='name']:contains('Tour Test Non-Teaching Type')))",
            content: "Record deleted — no longer in list",
        },
    ],
});
