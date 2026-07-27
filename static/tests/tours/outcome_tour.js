/** @odoo-module **/

import { registry } from "@web/core/registry";

// ems.outcome has no menu/action of its own — it only exists nested inside a subject's
// "Learning Outcome" tab (inline editable list) and, from there, its own popup form
// (opened via the "Edit" pencil button / open_form()). This tour exercises both: the
// embedded list row and the popup form, since neither a clean upgrade nor a
// TransactionCase test renders either of them in a browser.
registry.category("web_tour.tours").add("ems_outcome_crud", {
    test: true,
    url: "/odoo/action-ems.action_subject_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Subjects list view loaded",
        },
        {
            trigger: ".o_searchview .o_facet_remove",
            content: "Remove the default 'Group By: Studies' facet",
            run: "click",
        },
        // Create the parent subject that will host the tour's outcome
        {
            trigger: ".o_list_button_add",
            content: "Click New to create a subject",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='code'] input",
            content: "Fill in subject code",
            run: "edit 0TOUR2",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='acronym'] input",
            content: "Fill in subject acronym",
            run: "edit 0TOUR2",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='name'] input",
            content: "Fill in subject name",
            run: "edit Tour Subject For Outcome",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save the subject",
            run: "click",
        },
        // Go to the Learning Outcome tab and add an outcome inline
        {
            trigger: ".o_notebook .nav-link:contains('Learning Outcome')",
            content: "Open the Learning Outcome tab",
            run: "click",
        },
        // A single click on "Add a line" is occasionally lost with no visible effect and
        // no console error (confirmed by direct inspection) — most likely swallowed by a
        // reflow right as the empty list first turns editable, the same flakiness
        // documented and fixed the same way in withdrawal_tour.js: poll with a real delay
        // between attempts until the new editable row actually shows up.
        {
            trigger: ".o_field_widget[name='outcome_ids'] a:contains('Add a line')",
            content: "Add a new outcome row, retrying the click until it actually takes",
            run: async () => {
                const widget = document.querySelector(".o_field_widget[name='outcome_ids']");
                for (let attempt = 0; attempt < 20; attempt++) {
                    if (widget.querySelector(".o_selected_row")) break;
                    widget.querySelector("a")?.click();
                    await new Promise((resolve) => setTimeout(resolve, 300));
                }
            },
        },
        {
            trigger: ".o_field_widget[name='outcome_ids'] .o_selected_row",
            content: "Confirm the new outcome row is being edited",
        },
        {
            trigger: ".o_field_widget[name='outcome_ids'] [name='code'] input",
            content: "Fill in outcome code (must start with the subject's code)",
            run: "edit 0TOUR2_RA1",
        },
        {
            trigger: ".o_field_widget[name='outcome_ids'] [name='acronym'] input",
            content: "Fill in outcome acronym",
            run: "edit RA1",
        },
        {
            trigger: ".o_field_widget[name='outcome_ids'] [name='name'] input",
            content: "Fill in outcome name",
            run: "edit Tour Test Outcome",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save the subject with the new outcome",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='outcome_ids'] .o_data_row td[name='acronym']:contains('RA1')",
            content: "Outcome row saved in the embedded list",
        },
        // Open the outcome's own popup form via the pencil "Edit" button
        {
            trigger: ".o_field_widget[name='outcome_ids'] .o_data_row:has(td[name='acronym']:contains('RA1')) button[name='open_form']",
            content: "Open the outcome's own form (open_form popup)",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='name'] input",
            content: "Popup form opened — edit the name",
            run: "edit Tour Test Outcome Updated",
        },
        {
            trigger: ".modal-footer .o_form_button_save, .modal .o_form_button_save",
            content: "Save the popup form",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='outcome_ids'] .o_data_row td[name='name']:contains('Tour Test Outcome Updated')",
            content: "Updated name reflected back in the subject's embedded list",
        },
        // Delete the outcome row and save
        {
            trigger: ".o_field_widget[name='outcome_ids'] .o_data_row:has(td[name='acronym']:contains('RA1')) .o_list_record_remove button",
            content: "Delete the outcome row",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='outcome_ids']:not(:has(.o_data_row td[name='acronym']:contains('RA1')))",
            content: "Outcome row removed from the embedded list",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save the subject after removing the outcome",
            run: "click",
        },
        // Clean up: delete the tour's own subject
        {
            trigger: ".o_form_view .o_cp_action_menus button",
            content: "Open the subject's action menu",
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
            trigger: ".o_list_view",
            content: "Back in the subjects list after cleanup",
        },
    ],
});
