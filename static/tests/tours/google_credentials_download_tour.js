/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #478: "Download Google credentials" on the students list's Actions (cog) menu, run by a
// tutor. Selected student has no credentials PDF, so the action must answer with a warning
// instead of opening an empty download (the ZIP itself is covered by
// TestGoogleCredentialsDownloadRoute - a download tab can't be asserted from a tour).
registry.category("web_tour.tours").add("ems_google_credentials_download", {
    test: true,
    url: "/odoo/action-ems.action_student_kanban",
    steps: () => [
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to list view",
            run: "click",
        },
        {
            trigger: ".o_searchview_input",
            content: "Search for the seeded student",
            run: "edit GCT No Credentials",
        },
        {
            trigger: ".o_searchview_input",
            content: "Submit the search",
            run: "press Enter",
        },
        {
            trigger: ".o_data_row:has(.o_data_cell:contains('GCT No Credentials')) .o_list_record_selector",
            content: "Select the seeded student",
            run: "click",
        },
        {
            trigger: ".o_cp_action_menus button:has(.fa-cog)",
            content: "Open the list's Actions (cog) menu",
            run: "click",
        },
        {
            trigger: ".o_menu_item:contains('Download Google credentials')",
            content: "Click 'Download Google credentials'",
            run: "click",
        },
        {
            trigger: ".modal .modal-body:contains('Google credentials')",
            content: "The tutor is told there is nothing to download",
        },
    ],
});
