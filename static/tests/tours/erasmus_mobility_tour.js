/** @odoo-module **/

import { registry } from "@web/core/registry";
import { clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

// Issue #687 - Erasmus+ mobility preparation. Every tour runs against records seeded by
// tests/test_erasmus_mobility_tour.py and uses structural selectors (field names, values,
// classes), so the logged-in user's language does not matter.

// The Erasmus team checks the call's destinations, mobility documents and checklist, then
// opens the destination choice.
registry.category("web_tour.tours").add("ems_erasmus_open_choice", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_call",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='name']:contains('Test Erasmus Call')",
            content: "Open the call",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook a[name='preparation_documents']",
            content: "Open the mobility documents tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='preparation_document_ids'] .o_data_row td[name='sign_host']",
            content: "The documents say who signs them",
        },
        {
            trigger: ".o_form_view .o_notebook a[name='checklist']",
            content: "Open the checklist tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='task_ids'] .o_data_row",
            content: "The checklist has its steps",
        },
        {
            trigger: ".o_form_view .o_notebook a[name='destinations']",
            content: "Open the destinations tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='destination_ids'] td[name='name']:contains('Test destination 1')",
            content: "The destinations are listed",
        },
        ...clickAction("action_open_destination_choice", "Open destination choice"),
        {
            trigger: ".o_form_view .o_field_widget[name='choice_open'] input:checked",
            content: "The choice is open",
        },
    ],
});

// The Erasmus team reviews a document and ticks a step of a mobility in preparation.
registry.category("web_tour.tours").add("ems_erasmus_mobility_team", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_mobility",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='partner_id']:contains('Erasmus Test Student')",
            content: "Open the mobility",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='document_ids'] .o_data_row button[name='action_mark_valid']",
            content: "Mark the uploaded document as valid",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='document_ids'] .o_data_row td[name='file_state'] .badge.text-bg-success",
            content: "The document is complete once valid",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='document_ids'] .o_data_row td[name='file_category']:not(:empty)",
            content: "Each document shows its category in the record",
        },
        {
            trigger: ".o_form_view .o_notebook a[name='checklist']",
            content: "Open the checklist",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='task_ids'] .o_data_row:first td[name='done']",
            content: "Tick the first step (a boolean cell toggles on click)",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='task_ids'] .o_data_row:first td[name='done'] input:checked",
            content: "The step is ticked",
        },
        {
            trigger: ".o_form_view .o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_saved",
            content: "Saved",
        },
        ...clickAction("action_export_record", "Ask for the record's export"),
        {
            trigger: ".modal .o_form_view .o_field_widget[name='scope']",
            content: "The export dialog opens",
        },
        {
            trigger: ".modal .modal-footer .btn-secondary",
            content: "Cancel it",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal))",
            content: "The dialog is closed",
        },
    ],
});

// The Director validates a staff member's activity.
registry.category("web_tour.tours").add("ems_erasmus_mobility_director", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_mobility",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='partner_id']:contains('Erasmus Staff 1')",
            content: "Open the staff mobility",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook a[name='proposal']",
            content: "The proposal is shown",
        },
        ...clickAction("action_validate_proposal", "Validate the proposal"),
        {
            trigger: ".o_form_view .o_statusbar_status button[data-value='preparing'].o_arrow_button_current",
            content: "The mobility is in preparation",
        },
    ],
});

// The selected student chooses the destination in their turn on the portal.
registry.category("web_tour.tours").add("ems_erasmus_portal_choose", {
    test: true,
    steps: () => [
        {
            trigger: ".o_ems_erasmus_choose input[name='destination_id']:first",
            content: "Pick the first destination",
            run: "click",
        },
        {
            trigger: ".o_ems_erasmus_choose_submit",
            content: "Choose it",
            run: "click",
            expectUnloadPage: true,
        },
        {
            trigger: ".o_ems_erasmus_mobility .o_ems_erasmus_mobility_preparing",
            content: "The mobility is in preparation",
        },
        {
            trigger: ".o_ems_erasmus_mobility_documents .o_ems_erasmus_mobility_document",
            content: "The documents to hand in are listed",
        },
        {
            trigger: ".o_ems_erasmus_mobility_tasks li",
            content: "And the steps to follow",
        },
    ],
});
