/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #643: closing the enrollments nobody confirmed, from both places it is launched. Driven
// by a secretary (see test_enrollment_close_wizard_tour.py), who is the one closing enrollments.

const applyWizard = (name) => [
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
        trigger: ".o_notification:contains('1 deleted')",
        content: "The summary reports the deletion",
    },
    {
        trigger: "body:not(:has(.o_dialog))",
        content: "The wizard closed itself",
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
            trigger: ".o_list_view .o_control_panel:not(:has(button[name='action_send_enrollment_proposal']))",
            content: "No loose button in the header: every action is in the Action menu",
        },
        {
            trigger: ".o_cp_action_menus button:has(.fa-cog)",
            content: "Open the Action menu",
            run: "click",
        },
        {
            trigger: ".o_menu_item:contains('Send Enrollment')",
            content: "Send Enrollment moved into the Action menu",
        },
        {
            trigger: ".o_menu_item:contains('Close unconfirmed enrollments')",
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
        {
            trigger: ".o_list_view button[name='action_ems_close_unconfirmed']",
            content: "Close it from the Pre-inscripció header",
            run: "click",
        },
        ...applyWizard("Close Tour Never Offered"),
    ],
});
