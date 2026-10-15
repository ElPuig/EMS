/** @odoo-module **/

import { registry } from "@web/core/registry";
import { clickListHeaderAction } from "@ems/../tests/tours/actions_dropdown_helpers";

// Issue #643: closing the enrollments nobody confirmed, from both places it is launched. Driven
// by a secretary (see test_enrollment_close_wizard_tour.py), who is the one closing enrollments.

const applyWizard = (name) => [
    {
        trigger: ".o_dialog .o_field_widget[name='preview_html']:contains('Delete the person: 1')",
        content: "The summary says how many people get each action and what it means",
    },
    {
        trigger: `.o_dialog div[name='line_ids'] .o_data_row:has(td:contains('${name}')) td[name='action']:contains('Delete')`,
        content: "The preview tells what happens to the person: never a student, so deleted",
    },
    {
        trigger: ".o_dialog button[name='action_apply']",
        content: "Apply",
        run: "click",
    },
    {
        trigger: ".o_dialog:has(.modal-body:contains('cannot be undone')) .modal-footer .btn-primary",
        content: "Confirm",
        run: "click",
    },
    {
        trigger: ".o_dialog .o_field_widget[name='result_html']:contains('People processed: 1.')",
        content: "The result stays in the wizard",
    },
    {
        trigger: ".o_dialog .o_field_widget[name='log_file']",
        content: "with the log, which can be downloaded again",
    },
    {
        trigger: ".o_dialog footer button.btn-secondary",
        content: "Close",
        run: "click",
    },
    {
        trigger: "body:not(:has(.o_dialog))",
        content: "The wizard closed",
    },
];

registry.category("web_tour.tours").add("ems_enrollment_close_from_enrollments", {
    test: true,
    url: "/odoo/action-ems.action_ems_enrollments",
    steps: () => [
        {
            trigger: ".o_searchview_input",
            content: "Look for the seeded enrollment",
            run: "edit Close Tour Applicant",
        },
        { trigger: ".o_searchview_input", content: "Submit the search", run: "press Enter" },
        {
            trigger: ".o_data_row:has(.o_data_cell:contains('Close Tour Applicant')) .o_list_record_selector",
            content: "Select it",
            run: "click",
        },
        {
            trigger: ".o_list_selection_container:not(:has(> button[name='action_send_enrollment_proposal']))",
            content: "No loose button next to the selection: they are in the Actions dropdown",
        },
        {
            trigger: ".o_list_selection_container .o_ems_actions_toggle",
            content: "Open the Actions dropdown",
            run: "click",
        },
        {
            trigger: ".o_ems_actions_menu button[name='action_send_enrollment_proposal']",
            content: "Send Enrollment is in it too",
        },
        {
            trigger: ".o_ems_actions_menu button[name='action_ems_close_unconfirmed']",
            content: "Close the enrollment",
            run: "click",
        },
        ...applyWizard("Close Tour Applicant"),
    ],
});

registry.category("web_tour.tours").add("ems_enrollment_close_from_applicants", {
    test: true,
    url: "/odoo/action-ems.action_ems_applicants",
    steps: () => [
        {
            trigger: ".o_searchview .o_facet_remove",
            content: "Drop the default grouping, so the rows are listed",
            run: "click",
        },
        {
            trigger: ".o_searchview_dropdown_toggler",
            content: "Open the search options",
            run: "click",
        },
        {
            trigger: ".o_filter_menu .o-dropdown-item:contains('Without enrollment')",
            content: "Only the applicants who never got an offer",
            run: "click",
        },
        {
            trigger: ".o_searchview_input",
            content: "Look for both seeded applicants",
            run: "edit Close Tour",
        },
        { trigger: ".o_searchview_input", content: "Submit the search", run: "press Enter" },
        {
            trigger: ".o_list_view:not(:has(.o_data_cell:contains('Close Tour Offered')))",
            content: "The applicant holding an offer is filtered out",
        },
        {
            trigger: ".o_data_row:has(.o_data_cell:contains('Close Tour Never Offered')) .o_list_record_selector",
            content: "Select the applicant without enrollment",
            run: "click",
        },
        ...clickListHeaderAction("action_ems_close_unconfirmed", "Close it from the Actions menu"),
        ...applyWizard("Close Tour Never Offered"),
    ],
});
