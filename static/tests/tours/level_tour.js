/** @odoo-module **/

import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("ems_level_crud", {
    test: true,
    url: "/odoo/action-ems.level_action",
    steps: () => [
        // List view is loaded
        {
            trigger: ".o_list_view",
            content: "Levels list view loaded",
        },
        // Create a new level
        {
            trigger: ".o_list_button_add",
            content: "Click New to create a level",
            run: "click",
        },
        // Form view opens for a new record
        {
            trigger: ".o_form_view .o_field_widget[name='acronym'] input",
            content: "Form is ready — fill in acronym",
            run: "edit TOUR",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='name'] input",
            content: "Fill in name",
            run: "edit Tour Test Level",
        },
        // Save
        {
            trigger: ".o_form_button_save",
            content: "Save the new level",
            run: "click",
        },
        // Back to list — the save is confirmed when the record appears in the list
        {
            trigger: ".o_breadcrumb a",
            content: "Navigate back to the list",
            run: "click",
        },
        // Verify the new level appears in the list
        {
            trigger: ".o_list_view .o_data_row td[name='acronym']:contains('TOUR')",
            content: "New level confirmed in list",
        },
        // Open the record to edit
        {
            trigger: ".o_list_view .o_data_row td[name='name']:contains('Tour Test Level')",
            content: "Open level to edit",
            run: "click",
        },
        // The "Studies" embedded list tab (study_ids) had never been rendered by any tour.
        {
            trigger: ".o_notebook .nav-link:contains('Studies')",
            content: "Open the Studies tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='study_ids']",
            content: "The (empty) studies list renders without crashing",
        },
        // Edit the name
        {
            trigger: ".o_form_view .o_field_widget[name='name'] input",
            content: "Edit the name",
            run: "edit Tour Test Level Updated",
        },
        // Save the edit
        {
            trigger: ".o_form_button_save",
            content: "Save the updated name",
            run: "click",
        },
        // Verify update: back to list and check the new name
        {
            trigger: ".o_breadcrumb a",
            content: "Back to list to verify edit",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='name']:contains('Tour Test Level Updated')",
            content: "Updated name confirmed in list",
        },
        // Open record to delete it
        {
            trigger: ".o_list_view .o_data_row td[name='acronym']:contains('TOUR')",
            content: "Open level to delete",
            run: "click",
        },
        // Delete via the form action menu (gear)
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
        // Confirm deletion dialog
        {
            trigger: ".modal-footer .btn-primary",
            content: "Confirm deletion",
            run: "click",
        },
        // Back in list — record must be gone
        {
            trigger: ".o_list_view",
            content: "Back in list after deletion",
        },
        {
            trigger: ".o_list_view:not(:has(.o_data_row td[name='acronym']:contains('TOUR')))",
            content: "Level deleted — no longer in list",
        },
    ],
});
