/** @odoo-module **/

import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("ems_level_crud", {
    test: true,
    steps: () => [
        // Navigate to Levels via menu
        {
            trigger: 'a[data-menu-xmlid="ems.menu_community"]',
            content: "Open Educational Community menu",
            run: "click",
        },
        {
            trigger: 'a[data-menu-xmlid="ems.menu_community_config"]',
            content: "Open Configuration submenu",
            run: "click",
        },
        {
            trigger: 'a[data-menu-xmlid="ems.menu_levels"]',
            content: "Navigate to Levels",
            run: "click",
        },
        // Levels list view is loaded
        {
            trigger: ".o_list_view",
            content: "Levels list loaded",
        },
        // Create a new level
        {
            trigger: ".o_list_button_add",
            content: "Click New to create a level",
            run: "click",
        },
        // Fill in the acronym field
        {
            trigger: '.o_field_widget[name="acronym"] input',
            content: "Fill in acronym",
            run: "edit TOUR",
        },
        // Fill in the name field
        {
            trigger: '.o_field_widget[name="name"] input',
            content: "Fill in name",
            run: "edit Tour Test Level",
        },
        // Save the record
        {
            trigger: ".o_form_button_save",
            content: "Save the new level",
            run: "click",
        },
        // Verify the record is saved (acronym visible in form)
        {
            trigger: '.o_field_widget[name="acronym"] input[value="TOUR"]',
            content: "Verify acronym was saved",
        },
        // Go back to list
        {
            trigger: ".o_breadcrumb .o_back_button, .breadcrumb-item:first-child a",
            content: "Navigate back to the list",
            run: "click",
        },
        // Verify the new level appears in the list
        {
            trigger: ".o_list_view td[name='acronym']:contains('TOUR')",
            content: "New level appears in the list",
        },
        // Open the record again to edit it
        {
            trigger: ".o_list_view td[name='acronym']:contains('TOUR')",
            content: "Open the level to edit",
            run: "click",
        },
        // Edit the name
        {
            trigger: '.o_field_widget[name="name"] input',
            content: "Edit the name",
            run: "edit Tour Test Level Updated",
        },
        // Save the edit
        {
            trigger: ".o_form_button_save",
            content: "Save the edit",
            run: "click",
        },
        // Verify the updated name
        {
            trigger: '.o_field_widget[name="name"] input[value="Tour Test Level Updated"]',
            content: "Verify name was updated",
        },
        // Go back to list to delete
        {
            trigger: ".o_breadcrumb .o_back_button, .breadcrumb-item:first-child a",
            content: "Navigate back to list for deletion",
            run: "click",
        },
        // Select the record via checkbox
        {
            trigger: ".o_list_view .o_data_row td[name='acronym']:contains('TOUR')",
            content: "Click row to select the TOUR level",
            run: "click",
        },
        // Open the action/cog menu
        {
            trigger: ".o_cp_action_menus .o_dropdown_caret, .o_cp_action_menus button",
            content: "Open Action menu",
            run: "click",
        },
        // Click Delete
        {
            trigger: ".o_menu_item:contains('Delete'), .dropdown-item:contains('Delete')",
            content: "Select Delete option",
            run: "click",
        },
        // Confirm deletion
        {
            trigger: ".modal-dialog .btn-primary",
            content: "Confirm deletion",
            run: "click",
        },
        // Verify the level no longer appears in the list
        {
            trigger: ".o_list_view:not(:has(td[name='acronym']:contains('TOUR')))",
            content: "Level no longer in the list after deletion",
        },
    ],
});
