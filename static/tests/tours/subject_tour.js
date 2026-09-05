/** @odoo-module **/

import { registry } from "@web/core/registry";

// The production catalog has 200+ subjects and the list defaults to "Group By: Studies"
// (collapsed groups), so two things would hide the tour's own row: pagination past the
// first page (acronym-sorted) and the default grouping. Fixed by (1) removing the
// default group-by facet and (2) using a digit-prefixed acronym ("0TOUR") that always
// sorts first, so the row is on page 1 of the flat list regardless of catalog size.
registry.category("web_tour.tours").add("ems_subject_crud", {
    test: true,
    url: "/odoo/action-ems.action_subject_tree",
    steps: () => [
        // List view is loaded
        {
            trigger: ".o_list_view",
            content: "Subjects list view loaded",
        },
        {
            trigger: ".o_searchview .o_facet_remove",
            content: "Remove the default 'Group By: Studies' facet",
            run: "click",
        },
        // Create a new subject
        {
            trigger: ".o_list_button_add",
            content: "Click New to create a subject",
            run: "click",
        },
        // Form view opens for a new record
        {
            trigger: ".o_form_view .o_field_widget[name='code'] input",
            content: "Form is ready — fill in code",
            run: "edit 0TOUR_CODE",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='acronym'] input",
            content: "Fill in acronym",
            run: "edit 0TOUR",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='name'] input",
            content: "Fill in name",
            run: "edit Tour Test Subject",
        },
        // Save
        {
            trigger: ".o_form_button_save",
            content: "Save the new subject",
            run: "click",
        },
        // Back to list — the save is confirmed when the record appears in the list
        {
            trigger: ".o_breadcrumb a",
            content: "Navigate back to the list",
            run: "click",
        },
        // Verify the new subject appears in the list (first row: acronym sorts before
        // every existing letter-only acronym)
        {
            trigger: ".o_list_view .o_data_row td[name='acronym']:contains('0TOUR')",
            content: "New subject confirmed in list",
        },
        // Open the record to edit
        {
            trigger: ".o_list_view .o_data_row td[name='name']:contains('Tour Test Subject')",
            content: "Open subject to edit",
            run: "click",
        },
        // Edit the name
        {
            trigger: ".o_form_view .o_field_widget[name='name'] input",
            content: "Edit the name",
            run: "edit Tour Test Subject Updated",
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
            trigger: ".o_list_view .o_data_row td[name='name']:contains('Tour Test Subject Updated')",
            content: "Updated name confirmed in list",
        },
        // Open record to delete it
        {
            trigger: ".o_list_view .o_data_row td[name='acronym']:contains('0TOUR')",
            content: "Open subject to delete",
            run: "click",
        },
        // Delete via the form action menu (gear)
        {
            trigger: ".o_form_view .o_cp_action_menus button",
            content: "Open action menu",
            run: "click",
        },
        {
            // ems.subject has a unique 'code' constraint but no copy() override - the stock
            // "Duplicate" action would raise a raw UniqueViolation instead of working or
            // failing cleanly, so it's disabled (duplicate="0") until a real copy() is written.
            trigger: "body:not(:has(.o_menu_item:contains('Duplicate')))",
            content: "Duplicate is not offered (would crash on the unique code constraint)",
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
            trigger: ".o_list_view:not(:has(.o_data_row td[name='acronym']:contains('0TOUR')))",
            content: "Subject deleted — no longer in list",
        },
    ],
});
