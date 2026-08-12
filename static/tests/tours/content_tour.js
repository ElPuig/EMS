/** @odoo-module **/

import { registry } from "@web/core/registry";

// ems.content has no menu/action of its own: root items live in a subject's "Content" tab,
// and nested "Composite" children live inside a content item's own popup form
// (open_form()). This tour also regression-tests the view-context bug fixed in this DTON
// pass: views/community/content/form.xml's Composite tab used to default a new child's
// content_id to the *current record's own parent* instead of the current record itself,
// silently creating a sibling instead of a child with no error. Confirming the child shows
// up back inside the PARENT's own Composite list (not as a second root item) proves the fix.
//
// A plain declarative `run: "click"` on an x2many "Add a line" link is occasionally
// swallowed here with no visible effect and no console error — the same flakiness
// documented and fixed the same way in withdrawal_tour.js, outcome_tour.js and
// criteria_tour.js: retry the click, with a real delay between attempts.
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

registry.category("web_tour.tours").add("ems_content_crud", {
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
            run: "edit 0TOUR4",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='acronym'] input",
            content: "Fill in subject acronym",
            run: "edit 0TOUR4",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='name'] input",
            content: "Fill in subject name",
            run: "edit Tour Subject For Content",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save the subject",
            run: "click",
        },
        // Add a root content item
        {
            trigger: ".o_notebook .nav-link:contains('Content')",
            content: "Open the Content tab",
            run: "click",
        },
        addLineRetrying(".o_field_widget[name='content_ids']"),
        {
            trigger: ".o_field_widget[name='content_ids'] .o_selected_row [name='code'] input",
            content: "Fill in content code",
            run: "edit 0TOUR4_C1",
        },
        {
            trigger: ".o_field_widget[name='content_ids'] .o_selected_row [name='acronym'] input",
            content: "Fill in content acronym",
            run: "edit C1",
        },
        {
            trigger: ".o_field_widget[name='content_ids'] .o_selected_row [name='name'] input",
            content: "Fill in content name",
            run: "edit Tour Content",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save the subject with the new content",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='content_ids'] .o_data_row td[name='acronym']:contains('C1')",
            content: "Content row saved in the embedded list",
        },
        // Open the content's own popup form and add a Composite child
        {
            trigger: ".o_field_widget[name='content_ids'] .o_data_row:has(td[name='acronym']:contains('C1')) button[name='open_form']",
            content: "Open the content's own form (open_form popup)",
            run: "click",
        },
        {
            trigger: ".modal .o_notebook .nav-link:contains('Composite')",
            content: "Open the Composite tab in the content popup",
            run: "click",
        },
        addLineRetrying(".modal .o_field_widget[name='content_ids']"),
        {
            trigger: ".modal .o_field_widget[name='content_ids'] .o_selected_row [name='code'] input",
            content: "Fill in composite child code (must start with the parent's code)",
            run: "edit 0TOUR4_C1_A",
        },
        {
            trigger: ".modal .o_field_widget[name='content_ids'] .o_selected_row [name='acronym'] input",
            content: "Fill in composite child acronym",
            run: "edit C1A",
        },
        {
            trigger: ".modal .o_field_widget[name='content_ids'] .o_selected_row [name='name'] input",
            content: "Fill in composite child name",
            run: "edit Tour Composite Child",
        },
        {
            trigger: ".modal .o_form_button_save",
            content: "Save the content popup with the new composite child",
            run: "click",
        },
        // Saving closes both popups — re-open the root content's popup to confirm the
        // child is really nested under it (the regression check for the bug fix).
        {
            trigger: ".o_field_widget[name='content_ids']:not(:has(.modal)) .o_data_row td[name='acronym']:contains('C1')",
            content: "Back on the subject form after the popup closed",
        },
        {
            trigger: ".o_field_widget[name='content_ids'] .o_data_row:has(td[name='acronym']:contains('C1')) button[name='open_form']",
            content: "Re-open the root content's popup form",
            run: "click",
        },
        {
            trigger: ".modal .o_notebook .nav-link:contains('Composite')",
            content: "Open the Composite tab once more",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='content_ids'] .o_data_row td[name='acronym']:contains('C1A')",
            content: "REGRESSION CHECK: the composite child is nested under its real parent, "
                + "not floating as a second root item (the bug this DTON pass fixed)",
        },
        // Open the child's own popup and confirm it shows the correct read-only parent
        {
            trigger: ".modal .o_field_widget[name='content_ids'] .o_data_row:has(td[name='acronym']:contains('C1A')) button[name='open_form']",
            content: "Open the composite child's own form",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='content_id']:contains('C1')",
            content: "REGRESSION CHECK: the child's own form shows the correct read-only parent link",
        },
        {
            trigger: ".modal .o_form_button_save",
            content: "Close the child's popup (nothing to change)",
            run: "click",
        },
        // Clean up. The subject's Content list is flat (content_ids isn't filtered to root
        // items — it's the inverse of content.subject_id, which every level shares), so
        // both "C1" and "C1A" show up here; deleting the parent doesn't cascade-delete the
        // child (content_id isn't required, so its ondelete defaults to 'set null', not
        // 'cascade') — delete the child first, then the now-unambiguous root.
        {
            trigger: ".o_field_widget[name='content_ids']:not(:has(.modal)) .o_data_row td[name='acronym']:contains('C1')",
            content: "Back on the subject form",
        },
        {
            trigger: ".o_field_widget[name='content_ids'] .o_data_row:has(td[name='acronym']:contains('C1A')) .o_list_record_remove button",
            content: "Delete the composite child row first",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='content_ids']:not(:has(.o_data_row td[name='acronym']:contains('C1A')))",
            content: "Composite child row removed from the embedded list",
        },
        {
            trigger: ".o_field_widget[name='content_ids'] .o_data_row:has(td[name='acronym']:contains('C1')) .o_list_record_remove button",
            content: "Delete the (now unambiguous) root content row",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='content_ids']:not(:has(.o_data_row td[name='acronym']:contains('C1')))",
            content: "Content row removed from the embedded list",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save the subject after removing the content",
            run: "click",
        },
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
