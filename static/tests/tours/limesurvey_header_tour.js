/** @odoo-module **/

import { registry } from "@web/core/registry";

// ems.limesurvey_header.unlink() raises a RedirectWarning when deleting a CLOSED survey,
// redirecting through a confirmation server action (ems.action_limesurvey_delete_closed_confirmed)
// instead of a plain UserError - a real, standard Odoo dialog flow, but this specific
// EMS-authored message/redirect had never actually been driven through the delete UI in a
// browser. tests/test_limesurvey_header.py already covers the underlying unlink() logic
// directly (test_unlink_closed_without_flag_redirects/test_unlink_closed_with_flag_deletes) -
// this tour instead proves the real click path (select row -> Actions -> Delete -> confirm ->
// RedirectWarning dialog -> its own confirm button) actually reaches that logic and deletes.
registry.category("web_tour.tours").add("ems_limesurvey_header_delete_closed_confirmed", {
    test: true,
    url: "/odoo/action-ems.action_limesurvey_header_tree",
    steps: () => [
        { trigger: ".o_list_view", content: "Surveys list loaded" },
        {
            trigger: ".o_searchview_input",
            content: "Search for the seeded closed survey",
            run: "edit LimeSurvey Header Delete Tour",
        },
        { trigger: ".o_searchview_input", content: "Submit the search", run: "press Enter" },
        {
            trigger:
                ".o_data_row:has(.o_data_cell:contains('LimeSurvey Header Delete Tour')) .o_list_record_selector input",
            content: "Select the seeded closed survey",
            run: "click",
        },
        {
            trigger: ".o_cp_action_menus button",
            content: "Open the list's Actions (cog) menu",
            run: "click",
        },
        {
            trigger: ".o_menu_item:contains('Delete')",
            content: "Click Delete",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button:contains('Delete')",
            content: "Confirm the generic delete dialog",
            run: "click",
        },
        {
            trigger: ".modal button.btn-primary:contains('Yes, delete permanently')",
            content: "The RedirectWarning dialog shows the closed-survey warning - confirm the permanent delete",
            run: "click",
        },
        {
            trigger:
                ".o_list_view:not(:has(.o_data_cell:contains('LimeSurvey Header Delete Tour')))",
            content: "The survey is gone from the (reloaded, unfiltered) list",
        },
    ],
});
