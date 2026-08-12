/** @odoo-module **/

import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("ems_space_type_crud", {
    test: true,
    url: "/odoo/action-ems.action_space_type_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Space Types list view loaded",
        },
        {
            trigger: ".o_list_button_add",
            content: "Click New",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='name'] input",
            content: "Fill in name",
            run: "edit Tour Test Space Type",
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
            trigger: ".o_list_view .o_data_row td[name='name']:contains('Tour Test Space Type')",
            content: "New record confirmed in list",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='name']:contains('Tour Test Space Type')",
            content: "Open to edit",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='name'] input",
            content: "Edit the name",
            run: "edit Tour Test Space Type Updated",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save the edit",
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
        // Deleting can land Odoo on an adjacent record's form instead of the list (same
        // pattern already seen in workgroup_tour.js / non_teaching_type_tour.js).
        {
            trigger: ".o_list_view, .o_breadcrumb a",
            content: "Back in list after deletion (navigating there explicitly if needed)",
            run: () => {
                document.querySelector(".o_breadcrumb a")?.click();
            },
        },
        {
            trigger: ".o_list_view:not(:has(.o_data_row td[name='name']:contains('Tour Test Space Type Updated')))",
            content: "Record deleted — no longer in list",
        },
    ],
});
