/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #507: the family reviews and completes the contact details from the portal, reaching the
// page from the Profile tab's button. Structural selectors (input names, hrefs) wherever possible,
// so the portal user's language barely matters.
registry.category("web_tour.tours").add("ems_contact_data_portal", {
    test: true,
    url: "/my/account",
    steps: () => [
        {
            trigger: ".o_portal_details a[href='/my/dades-contacte']",
            content: "Open the contact details review from the profile",
            run: "click",
        },
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
            content: "Send, and check the screen says what is happening while it runs",
            // No step can target the overlay: the tour engine waits for `.o_blockUI` to go away
            // before it looks for any trigger. The test slows the server down so it is still up.
            run: async (helpers) => {
                await helpers.click();
                await new Promise((resolve) => setTimeout(resolve, 500));
                const message = document.querySelector(".o_blockUI .o_message");
                if (!message || !message.textContent.includes("Processing the requests")) {
                    throw new Error("The processing overlay was not shown while sending");
                }
            },
        },
        {
            trigger: "body:not(:has(.o_dialog))",
            content: "The assistant closed after sending, and the screen is free again",
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

// Educational Community opens the Students list, and its Students section (a dropdown, since it now
// holds two entries) leads to Student Data. Selectors are the menus' xmlids: the labels are translated.
registry.category("web_tour.tours").add("ems_contact_data_menu", {
    test: true,
    url: "/odoo",
    steps: () => [
        {
            trigger: ".o_navbar_apps_menu button[data-hotkey='h']",
            content: "Open the apps menu",
            run: "click",
        },
        {
            trigger: ".o-dropdown--menu .o_app[data-menu-xmlid='ems.menu_community']",
            content: "Open Educational Community",
            run: "click",
        },
        {
            trigger: ".o_action_manager .o_kanban_view",
            content: "It opens the Students list by default",
        },
        {
            trigger: ".o_menu_sections button[data-menu-xmlid='ems.menu_students_root']",
            content: "Open the Students section",
            run: "click",
        },
        {
            trigger: ".o-dropdown--menu .dropdown-item[data-menu-xmlid='ems.menu_students']",
            content: "The section offers the Students list",
        },
        {
            trigger: ".o-dropdown--menu .dropdown-item[data-menu-xmlid='ems.menu_contact_data_requests']",
            content: "and Student Data",
            run: "click",
        },
        {
            trigger: ".o_action_manager .o_list_view",
            content: "Student Data lists the contact data requests",
        },
    ],
});
