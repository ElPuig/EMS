/** @odoo-module **/

import { registry } from "@web/core/registry";

// ems.portal.access.wizard has no menu/act_window of its own - it only opens via the
// "Portal access (students/families)" server action bound to the students list's cog
// ("Actions") menu (see action_portal_access_bulk in portal_access_wizard.xml), the same
// selection-then-cog-action mechanic already proven working by withdrawal_tour.js's bulk
// Archive tours. This tour additionally exercises widget="radio" on the `mode` field, using
// the label-click + input:checked pattern already established by limesurvey_block_tour.js.
registry.category("web_tour.tours").add("ems_portal_access_wizard_revoke", {
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
            trigger: ".o_list_view",
            content: "List view rendered",
        },
        // 1111+ students in this dev DB, sorted alphabetically and paginated 80/page - the
        // seeded student ('Portal Wizard Tour Student', starting with 'P') is nowhere near
        // page 1, so it must be searched for rather than assumed visible.
        {
            trigger: ".o_searchview_input",
            content: "Search for the seeded student by name",
            run: "edit Portal Wizard Tour Student",
        },
        {
            trigger: ".o_searchview_input",
            content: "Submit the search",
            run: "press Enter",
        },
        {
            trigger:
                ".o_data_row:has(.o_data_cell:contains('Portal Wizard Tour Student')) .o_list_record_selector",
            content: "Select the seeded student",
            run: "click",
        },
        {
            trigger: ".o_cp_action_menus button",
            content: "Open the list's Actions (cog) menu",
            run: "click",
        },
        // Odoo's :contains() is case-insensitive, so a narrower "Portal access" would also
        // match the unrelated, native "Grant Portal Access" action (portal.wizard) that's
        // bound to this same list - "students/families" is unique to this action's own name.
        {
            trigger: ".o_menu_item:contains('students/families')",
            content: "Click 'Portal access (students/families)'",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='mode'] input[type='radio']:checked",
            content: "The wizard opened with 'Grant access' selected by default",
        },
        {
            trigger: ".modal .o_field_widget[name='line_ids'] .o_data_row td:contains('portal.wizard.tour.student@example.com')",
            content: "The preview lists the student as recipient",
        },
        {
            trigger: ".modal .o_field_widget[name='mode'] label:contains('Revoke access')",
            content: "Select the 'Revoke access' radio option",
            run: "click",
        },
        {
            trigger:
                ".modal .o_field_widget[name='mode'] .o_radio_item:has(label:contains('Revoke access')) input[type='radio']:checked",
            content: "The radio option is actually selected (not just clicked)",
        },
        {
            trigger: ".modal footer button[name='action_apply']",
            content: "Apply — revoke portal access for the selected student",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal))",
            content: "The wizard dialog closed after a successful apply",
        },
    ],
});
