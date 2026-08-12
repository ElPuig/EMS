/** @odoo-module **/

import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("ems_space_crud", {
    test: true,
    url: "/odoo/action-ems.action_space_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Spaces list view loaded",
        },
        {
            trigger: ".o_list_button_add",
            content: "Click New",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='work_location_id'] input",
            content: "Search for the Main building work location",
            run: "edit Main building",
        },
        {
            trigger: ".o-autocomplete--dropdown-menu li:contains('Main building')",
            content: "Select Main building",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='code'] input",
            content: "Fill in code",
            run: "edit TOUR-SPACE",
        },
        {
            trigger: ".o_field_widget[name='space_type_id'] input",
            content: "Type a new space type name",
            run: "edit Tour Space Type",
        },
        {
            trigger: ".o-autocomplete--dropdown-menu li:contains('Create \"Tour Space Type\"')",
            content: "Create the space type on the fly",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='name'] input",
            content: "Fill in name",
            run: "edit Tour Test Space",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save the new space",
            run: "click",
        },
        {
            trigger: ".o_breadcrumb a",
            content: "Navigate back to the list",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row td:contains('Tour Test Space')",
            content: "New space confirmed in list",
        },
        {
            trigger: ".o_list_view .o_data_row td:contains('Tour Test Space')",
            content: "Open to delete",
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
        {
            trigger: ".o_list_view, .o_breadcrumb a",
            content: "Back in list after deletion (navigating there explicitly if needed)",
            run: () => {
                document.querySelector(".o_breadcrumb a")?.click();
            },
        },
        {
            trigger: ".o_list_view:not(:has(.o_data_row td:contains('Tour Test Space')))",
            content: "Space deleted — no longer in list",
        },
    ],
});
