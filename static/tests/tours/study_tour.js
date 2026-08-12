/** @odoo-module **/

import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("ems_study_crud", {
    test: true,
    url: "/odoo/action-ems.action_study_tree",
    steps: () => [
        // List view is loaded
        {
            trigger: ".o_list_view",
            content: "Studies list view loaded",
        },
        // Create a new study
        {
            trigger: ".o_list_button_add",
            content: "Click New to create a study",
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
            run: "edit Tour Test Study",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='code'] input",
            content: "Fill in code",
            run: "edit TOUR_CODE",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='date'] input",
            content: "Fill in release date",
            run: "edit 09/01/2024",
        },
        // Save
        {
            trigger: ".o_form_button_save",
            content: "Save the new study",
            run: "click",
        },
        // Back to list — the save is confirmed when the record appears in the list
        {
            trigger: ".o_breadcrumb a",
            content: "Navigate back to the list",
            run: "click",
        },
        // Verify the new study appears in the list
        {
            trigger: ".o_list_view .o_data_row td[name='acronym']:contains('TOUR')",
            content: "New study confirmed in list",
        },
        // Open the record to edit
        {
            trigger: ".o_list_view .o_data_row td[name='name']:contains('Tour Test Study')",
            content: "Open study to edit",
            run: "click",
        },
        // The "Subjects" and "Attached files" embedded list tabs had never been rendered by
        // any tour (outcome_tour.js/criteria_tour.js/content_tour.js all reach the Subject's
        // own tabs, not the Study form's).
        {
            trigger: ".o_notebook .nav-link:contains('Subjects')",
            content: "Open the Subjects tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='subject_ids']",
            content: "The (empty) subjects list renders without crashing",
        },
        {
            trigger: ".o_notebook .nav-link:contains('Attached files')",
            content: "Open the Attached files tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='attachment_ids']",
            content: "The (empty) attachments list renders without crashing",
        },
        // Edit the name
        {
            trigger: ".o_form_view .o_field_widget[name='name'] input",
            content: "Edit the name",
            run: "edit Tour Test Study Updated",
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
            trigger: ".o_list_view .o_data_row td[name='name']:contains('Tour Test Study Updated')",
            content: "Updated name confirmed in list",
        },
        // Open record to delete it
        {
            trigger: ".o_list_view .o_data_row td[name='acronym']:contains('TOUR')",
            content: "Open study to delete",
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
            content: "Study deleted — no longer in list",
        },
    ],
});
