/** @odoo-module **/

import { registry } from "@web/core/registry";

// Opens a freshly seeded student (created by the Python test, not a real production
// contact — see test_contact_tour.py) so this tour is free to actually create data:
// clicks through the student-only tabs to confirm none of them crash on render, then
// exercises the "Add contact" relation wizard end-to-end (ems.contact.relation.wizard),
// which had zero coverage before this pass.
//
// A plain declarative `run: "click"` on an x2many "Add a line" link is occasionally
// swallowed here with no visible effect and no console error - the same flakiness
// documented and fixed the same way in content_tour.js/withdrawal_tour.js/outcome_tour.js/
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

registry.category("web_tour.tours").add("ems_contact_tabs_and_relation_wizard", {
    test: true,
    url: "/odoo/action-ems.action_student_kanban",
    steps: () => [
        {
            trigger: ".o_control_panel",
            content: "Educational Community loaded",
        },
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to list view",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('Contact Tour Student')",
            content: "Open the seeded student",
            run: "click",
        },
        {
            trigger: ".o_form_view label:contains('Personal email')",
            content: "The generic 'Email' row is relabeled for a student (no ambiguity with the institutional address)",
        },
        {
            trigger: ".o_form_view label:contains('Corporate email')",
            content: "The read-only 'Corporate email' row mirrors student_email",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='student_email']:contains('contact.tour.student@example.com')",
            content: "...and shows the same address stored on the student",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Student data')",
            content: "Open the Student data tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='is_adult']",
            content: "Student data tab rendered without crashing",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Studies')",
            content: "Open the Studies tab",
            run: "click",
        },
        addLineRetrying(".o_field_widget[name='enrollment_ids']"),
        {
            trigger: ".o_field_widget[name='enrollment_ids'] .o_selected_row [name='subject_id'] input",
            content: "Pick the subject for the new enrollment line",
            run: "edit Test Subject (Contact Tour)",
        },
        {
            trigger: ".o-autocomplete--dropdown-menu li:contains('Test Subject (Contact Tour)')",
            content: "Select the subject",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='enrollment_ids'] .o_selected_row [name='group_id'] input",
            content: "REGRESSION CHECK: pick a reinforcement group as the teaching group - the view's "
                + "domain used to only allow groups matching the student's own study, which a "
                + "reinforcement group (no study by design) could never satisfy",
            run: "edit Test Reinforcement Group (Contact Tour)",
        },
        {
            trigger: ".o-autocomplete--dropdown-menu li:contains('Test Reinforcement Group (Contact Tour)')",
            content: "Select the reinforcement group",
            run: "click",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save the student with the new subject enrollment",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='enrollment_ids'] .o_data_row td[name='group_id']:contains('Test Reinforcement Group (Contact Tour)')",
            content: "The enrollment line persisted with the reinforcement group as its teaching group",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Secretary')",
            content: "Open the Secretary tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='benefit_ids']",
            content: "Secretary tab (benefit_ids) rendered without crashing",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Contacts & Addresses')",
            content: "Open the Contacts & Addresses tab, home of the relation wizard button",
            run: "click",
        },
        {
            trigger: ".o_form_view button[name='action_open_relation_wizard']",
            content: "Click Add contact",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='type_selection_id'] input",
            content: "Choose a relation type",
            run: "edit Father",
        },
        {
            trigger: ".o-autocomplete--dropdown-menu li:contains('Father')",
            content: "Select the Father relation type",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='is_new_contact'] input",
            content: "Check 'New contact' to reveal the new-contact fields",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='firstname'] input",
            content: "Fill in first name",
            run: "edit Tour",
        },
        {
            trigger: ".modal .o_field_widget[name='lastname'] input",
            content: "Fill in last name",
            run: "edit Father",
        },
        {
            trigger: ".modal .o_field_widget[name='phone'] input",
            content: "Fill in phone (at least one contact method is required)",
            run: "edit 600000000",
        },
        {
            trigger: ".modal .o_field_widget[name='document_id'] input",
            content: "Fill in document ID (at least one identification document is required)",
            run: "edit 12345678A",
        },
        {
            trigger: ".modal-footer .btn-primary",
            content: "Save the new family contact",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='relation_all_ids'] .o_data_row td:contains('Tour Father')",
            content: "The new relation shows up in the Addresses tab list",
        },
    ],
});
