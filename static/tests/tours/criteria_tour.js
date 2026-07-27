/** @odoo-module **/

import { registry } from "@web/core/registry";

// ems.criteria has no menu/action of its own — it is nested two levels deep: a subject's
// "Learning Outcome" tab holds outcomes, and each outcome's own popup form (open_form())
// holds an "Evaluation criteria" tab with criteria, which in turn have their own popup
// form. This tour walks the full chain, since neither a clean upgrade nor a
// TransactionCase test renders any of these three view layers in a browser.
//
// A plain declarative `run: "click"` on an x2many "Add a line" link is occasionally
// swallowed here with no visible effect and no console error — the same flakiness
// documented and fixed the same way in withdrawal_tour.js and outcome_tour.js: retry the
// click, with a real delay between attempts, until the new editable row actually shows up.
// NOTE: the retry loop must use plain DOM APIs only (document.querySelector doesn't
// understand the tour engine's own `:contains()` extension — using it here throws a
// SyntaxError, confirmed the hard way) — scope retries to a plain-selectable ancestor
// and use querySelector("a")/[".o_selected_row"] etc. from there, same as below.
function addLineRetrying(widgetSelector) {
    return {
        trigger: `${widgetSelector} a:contains('Add a line')`,
        content: `Add a new row in ${widgetSelector}, retrying the click until it takes`,
        run: async () => {
            const widget = document.querySelector(widgetSelector);
            for (let attempt = 0; attempt < 20; attempt++) {
                if (widget.querySelector(".o_selected_row")) break;
                widget.querySelector("a")?.click();
                await new Promise((resolve) => setTimeout(resolve, 300));
            }
        },
    };
}

registry.category("web_tour.tours").add("ems_criteria_crud", {
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
        // Create the parent subject
        {
            trigger: ".o_list_button_add",
            content: "Click New to create a subject",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='code'] input",
            content: "Fill in subject code",
            run: "edit 0TOUR3",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='acronym'] input",
            content: "Fill in subject acronym",
            run: "edit 0TOUR3",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='name'] input",
            content: "Fill in subject name",
            run: "edit Tour Subject For Criteria",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save the subject",
            run: "click",
        },
        // Add the parent outcome
        {
            trigger: ".o_notebook .nav-link:contains('Learning Outcome')",
            content: "Open the Learning Outcome tab",
            run: "click",
        },
        addLineRetrying(".o_field_widget[name='outcome_ids']"),
        {
            trigger: ".o_field_widget[name='outcome_ids'] .o_selected_row [name='code'] input",
            content: "Fill in outcome code (must start with the subject's code)",
            run: "edit 0TOUR3_RA1",
        },
        {
            trigger: ".o_field_widget[name='outcome_ids'] .o_selected_row [name='acronym'] input",
            content: "Fill in outcome acronym",
            run: "edit RA1",
        },
        {
            trigger: ".o_field_widget[name='outcome_ids'] .o_selected_row [name='name'] input",
            content: "Fill in outcome name",
            run: "edit Tour Outcome For Criteria",
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
        // Open the outcome's own popup form
        {
            trigger: ".o_field_widget[name='outcome_ids'] .o_data_row:has(td[name='acronym']:contains('RA1')) button[name='open_form']",
            content: "Open the outcome's own form (open_form popup)",
            run: "click",
        },
        {
            trigger: ".modal .o_notebook .nav-link:contains('Evaluation criteria')",
            content: "Open the Evaluation criteria tab in the outcome popup",
            run: "click",
        },
        addLineRetrying(".modal .o_field_widget[name='criteria_ids']"),
        {
            trigger: ".modal .o_field_widget[name='criteria_ids'] .o_selected_row [name='code'] input",
            content: "Fill in criteria code (must start with the outcome's code)",
            run: "edit 0TOUR3_RA1_A",
        },
        {
            trigger: ".modal .o_field_widget[name='criteria_ids'] .o_selected_row [name='acronym'] input",
            content: "Fill in criteria acronym",
            run: "edit CA1",
        },
        {
            trigger: ".modal .o_field_widget[name='criteria_ids'] .o_selected_row [name='name'] input",
            content: "Fill in criteria name",
            run: "edit Tour Test Criteria",
        },
        {
            trigger: ".modal .o_form_button_save",
            content: "Save the outcome popup with the new criteria",
            run: "click",
        },
        // Re-open the outcome popup to confirm the criteria row was persisted
        {
            trigger: ".o_field_widget[name='outcome_ids'] .o_data_row:has(td[name='acronym']:contains('RA1')) button[name='open_form']",
            content: "Re-open the outcome's popup form",
            run: "click",
        },
        {
            trigger: ".modal .o_notebook .nav-link:contains('Evaluation criteria')",
            content: "Open the Evaluation criteria tab again",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='criteria_ids'] .o_data_row td[name='acronym']:contains('CA1')",
            content: "Criteria row confirmed in the outcome's embedded list",
        },
        // Open the criteria's own popup form (nested inside the outcome's modal)
        {
            trigger: ".modal .o_field_widget[name='criteria_ids'] .o_data_row:has(td[name='acronym']:contains('CA1')) button[name='open_form']",
            content: "Open the criteria's own form (open_form popup)",
            run: "click",
        },
        // The outcome popup closes itself when the criteria popup opens on top of it (only
        // one .modal exists at a time, not two nested ones).
        {
            trigger: ".modal .o_field_widget[name='name'] input",
            content: "Criteria's own popup opened — edit the name",
            run: "edit Tour Test Criteria Updated",
        },
        {
            trigger: ".modal .o_form_button_save",
            content: "Save the criteria's own popup",
            run: "click",
        },
        // Saving the criteria popup closes it AND the outcome popup underneath it (there
        // is nothing left to return to but the subject form) — re-open the outcome popup
        // to confirm the update and continue managing its criteria.
        {
            trigger: ".o_form_view:not(:has(.modal)) .o_breadcrumb:contains('Tour Subject For Criteria')",
            content: "Back on the subject form after both popups closed",
        },
        {
            trigger: ".o_field_widget[name='outcome_ids'] .o_data_row:has(td[name='acronym']:contains('RA1')) button[name='open_form']",
            content: "Re-open the outcome's popup form to confirm the criteria update",
            run: "click",
        },
        {
            trigger: ".modal .o_notebook .nav-link:contains('Evaluation criteria')",
            content: "Open the Evaluation criteria tab once more",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='criteria_ids'] .o_data_row td[name='name']:contains('Tour Test Criteria Updated')",
            content: "Updated name reflected back in the outcome's embedded list",
        },
        // Delete the criteria row and save the outcome popup
        {
            trigger: ".modal .o_field_widget[name='criteria_ids'] .o_data_row:has(td[name='acronym']:contains('CA1')) .o_list_record_remove button",
            content: "Delete the criteria row",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='criteria_ids']:not(:has(.o_data_row td[name='acronym']:contains('CA1')))",
            content: "Criteria row removed from the embedded list",
        },
        {
            trigger: ".modal .o_form_button_save",
            content: "Save the outcome popup after removing the criteria",
            run: "click",
        },
        // Clean up: delete the tour's own subject (cascades the outcome with it)
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
