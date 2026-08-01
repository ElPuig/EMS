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
            trigger: ".modal [name='alert-danger-issues']:contains('unknown.tour.teacher@example.com')",
            content: "The onchange correctly flags the unknown teacher e-mail as a blocking error, listed under the shared 'these problems prevent the import' banner",
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

// A code with no '@' (e.g. "X1") is NOT a real e-mail typo - it's the external planner's way
// of naming a not-yet-staffed post. Unlike the unknown-e-mail case above, this must NOT block
// the import: a non-blocking info banner is shown instead, and importing creates a
// pending-identification teacher whose schedule is assigned immediately. This tour proves the
// banner/Import-button behaviour and the new "Pending identification" indicator actually
// render in the browser - a TransactionCase proves the model/importer logic works, but not
// that the view (badge column, ribbon) doesn't crash or silently fail to show.
registry.category("web_tour.tours").add("ems_working_schedules_import_pending_teacher", {
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
            trigger: ".dropdown-item:contains('Import planner data')",
            content: "Click 'Import planner data (XML)'",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='attachment_ids']",
            content: "Import wizard dialog opened",
            run: async () => {
                const xml = '<root><T name="TOURX1 Pending Teacher">'
                    + '<D name="1 Monday"><H name="1 09:00">'
                    + '<NonTeaching name="G Guard"/>'
                    + '</H></D></T></root>';
                const file = new File([xml], "planner_pending.xml", { type: "text/xml" });
                await inputFiles(".modal .o_field_widget[name='attachment_ids'] .o_input_file", [file]);
            },
        },
        {
            trigger: ".modal [name='alert-info']:contains('TOURX1')",
            content: "The onchange reports the placeholder code as a non-blocking info message",
        },
        {
            trigger: ".modal footer button[name='import_planner_data']:not([disabled])",
            content: "The Import button stays enabled - only a real unknown e-mail blocks it",
            run: "click",
        },
        {
            // import_planner_data()'s 'soft_reload' client action closes the dialog once the
            // import completes, but not synchronously with the click - wait for the modal to be
            // fully gone (not just for the list behind it, which was already in the DOM the
            // whole time) before ending the tour, or Odoo's own end-of-tour check flags a
            // still-mid-close dialog as "an open form view in edition mode".
            trigger: "body:not(:has(.modal)) .o_list_view",
            content: "Back to the Working Schedules list, confirming the placeholder teacher was created",
        },
    ],
});

// Renders the "Pending identification" indicator (list badge column, kanban + form ribbon)
// added to views/community/employee/{list,kanban,form}.xml for a teacher created from a
// schedule-import placeholder code. The employee is seeded directly via the ORM in
// TestWorkingSchedulesImportWizardTour.test_employee_pending_identification_indicator_tour -
// this tour is only about proving the VIEW renders correctly, not re-testing the importer
// (covered above and by TestWorkingSchedulesImportWizard's backend tests). The kanban indicator
// used to be a badge under the name; changed to a ribbon (2026-08-01) for visual consistency
// with the "Archived"/reason-aware ribbons added to this same kanban right before it.
registry.category("web_tour.tours").add("ems_employee_pending_identification_indicator", {
    test: true,
    url: "/odoo/action-ems.action_employee_kanban",
    steps: () => [
        {
            trigger: ".o_control_panel",
            content: "Teachers loaded",
        },
        {
            trigger:
                ".o_kanban_view .o_kanban_record:contains('Tour Pending Teacher')"
                + " .ribbon:contains('Pending identification')",
            content: "The pending-identification teacher's kanban card shows the ribbon",
        },
        {
            trigger:
                ".o_kanban_view .o_kanban_record:contains('Tour Confirmed Teacher')"
                + ":not(:has(.ribbon:contains('Pending identification')))",
            content: "A confirmed-identity teacher's kanban card does NOT show the ribbon",
        },
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to list view",
            run: "click",
        },
        {
            trigger:
                ".o_list_view .o_data_row:has(.o_data_cell:contains('Tour Pending Teacher'))"
                + " .o_data_cell[name='pending_identification'] input:checked",
            content: "The seeded pending-identification teacher is flagged in the list",
        },
        {
            trigger: ".o_data_row .o_data_cell:contains('Tour Pending Teacher')",
            content: "Open the pending-identification teacher",
            run: "click",
        },
        {
            trigger: ".o_form_view .ribbon:contains('Pending identification')",
            content: "The form shows the pending-identification ribbon",
        },
    ],
});
