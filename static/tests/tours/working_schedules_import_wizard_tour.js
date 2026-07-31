/** @odoo-module **/

import { registry } from "@web/core/registry";
import { inputFiles } from "@web/../tests/utils";

// ems.working_schedules_import_wizard has no static ir.actions.act_window record - it's only
// ever opened dynamically (doAction() with a plain dict) from the "Working Schedules" list's
// cog menu (static/src/js/backend/import_planner_cog_menu.js, isDisplayed gated on
// actionName === "Working Schedules") or from an employee's own Schedule tab. This tour
// reaches it the same way a real user would: navigate to the list, open the cog menu, click
// "Import: planner data". widget="many2many_binary" (attachment_ids) had zero browser
// coverage. Rather than building a full valid planner XML (a real schedule-entry format, out
// of scope for what this gap is actually about), this exercises a real, simple path: an XML
// naming a teacher e-mail that doesn't exist yet, which the wizard's own onchange correctly
// reports as a blocking error - proving the upload widget and its onchange both work.
registry.category("web_tour.tours").add("ems_working_schedules_import_unknown_teacher", {
    test: true,
    url: "/odoo/action-ems.action_working_schedules_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Working Schedules list loaded",
        },
        {
            trigger: ".o_cp_action_menus button",
            content: "Open the list's Actions (cog) menu",
            run: "click",
        },
        {
            // This custom cog-menu entry (import_planner_cog_menu.js) uses the raw
            // <DropdownItem> component directly, which renders "o-dropdown-item
            // dropdown-item" - not Odoo's own ".o_menu_item" wrapper class used by the
            // standard cog-menu entries (Import records/Export All) alongside it.
            trigger: ".dropdown-item:contains('Import planner data')",
            content: "Click 'Import planner data (XML)'",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='attachment_ids']",
            content: "Import wizard dialog opened",
            run: async () => {
                const xml = '<root><teacher name="unknown.tour.teacher@example.com Unknown Teacher"></teacher></root>';
                const file = new File([xml], "planner.xml", { type: "text/xml" });
                await inputFiles(".modal .o_field_widget[name='attachment_ids'] .o_input_file", [file]);
            },
        },
        {
            trigger: ".modal .o_field_widget[name='attachment_ids'] .o_attachment",
            content: "File attached",
        },
        {
            trigger: ".modal [name='alert-danger']:contains('unknown.tour.teacher@example.com')",
            content: "The onchange correctly flags the unknown teacher e-mail as a blocking error",
        },
        {
            trigger: ".modal footer:not(:has(button[name='import_planner_data']))",
            content: "The Import button is hidden while the blocking error is present",
        },
        {
            // Close the still-dirty dialog explicitly - otherwise Odoo's own test harness
            // flags "Tour finished with an open form view in edition mode" as a failure.
            trigger: ".modal footer button[name='cancel']",
            content: "Close the wizard",
            run: "click",
        },
    ],
});
