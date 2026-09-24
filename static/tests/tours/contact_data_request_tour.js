/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #507: the family reviews and completes the contact details from the portal. Structural
// selectors (input names) wherever possible, so the portal user's language barely matters.
registry.category("web_tour.tours").add("ems_contact_data_portal", {
    test: true,
    url: "/my/dades-contacte",
    steps: () => [
        {
            trigger: ".o_ems_contact_data_form input[name='s_street']",
            content: "Fill in the student's street",
            run: "edit Tour Portal Street 5",
        },
        {
            trigger: ".o_ems_contact_data_form input[name='s_zip']",
            run: "edit 08925",
        },
        {
            trigger: ".o_ems_contact_data_form input[name='s_city']",
            run: "edit Tour City",
        },
        {
            trigger: ".o_ems_contact_data_form input[name='s_document_id']",
            content: "Fill in the student's DNI",
            run: "edit 10000007K",
        },
        {
            trigger: ".o_ems_family_entry input[name$='_lastname']",
            content: "Complete the last name of the family contact on file",
            run: "edit Tour",
        },
        {
            trigger: ".o_ems_add_family",
            content: "Add a second family contact",
            run: "click",
        },
        {
            trigger: ".o_ems_new_family_container select[name='n0_relation_type_id']",
            run: "selectByLabel Father",
        },
        {
            trigger: ".o_ems_new_family_container input[name='n0_firstname']",
            run: "edit Tour",
        },
        {
            trigger: ".o_ems_new_family_container input[name='n0_lastname']",
            run: "edit Father",
        },
        {
            trigger: ".o_ems_new_family_container input[name='n0_mobile']",
            run: "edit 711200008",
        },
        {
            trigger: ".o_ems_contact_data_submit",
            content: "Send the details for review",
            run: "click",
        },
        {
            trigger: ".o_ems_contact_data_sent",
            content: "The details were sent",
        },
    ],
});

// The group's tutor sends a request to their group from the follow-up list, then opens a family's
// answer (the action's second view mode) and approves it.
registry.category("web_tour.tours").add("ems_contact_data_tutor", {
    test: true,
    url: "/odoo/action-ems.action_ems_contact_data_request",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row:contains('Minor Student (TCDT)')",
            content: "The follow-up list shows the tutor's student",
        },
        {
            trigger: ".o_control_panel button:contains('Request contact data')",
            content: "Open the request assistant",
            run: "click",
        },
        {
            trigger: ".o_dialog div[name='group_ids'] input",
            content: "Pick their own group",
            run: "edit TCDTS",
        },
        {
            trigger: ".o-autocomplete--dropdown-item a:contains(TCDTS)",
            run: "click",
        },
        {
            trigger: ".o_dialog div[name='only_incomplete'] input",
            content: "Also ask the students whose data looks complete",
            run: "click",
        },
        {
            trigger: ".o_dialog div[name='line_ids'] .o_data_row td:contains('Adult Student (TCDT)')",
            content: "The preview lists who is about to be asked",
        },
        {
            trigger: ".o_dialog button[name='action_apply']",
            content: "Send",
            run: "click",
        },
        {
            trigger: "body:not(:has(.o_dialog))",
            content: "The assistant closed after sending",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('Minor Student (TCDT)') .o_data_cell",
            content: "Open the answered request",
            run: "click",
        },
        {
            trigger: ".o_form_view div[name='line_ids'] .o_data_row",
            content: "The form lists the changes to review",
        },
        {
            trigger: ".o_form_view button[name='action_approve']",
            content: "Approve them",
            run: "click",
        },
        {
            trigger: ".o_form_view:not(:has(button[name='action_approve']))",
            content: "Approved: nothing left to approve",
        },
    ],
});
