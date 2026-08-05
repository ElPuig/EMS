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
// naming a teacher e-mail that doesn't exist yet.
//
// Changed 2026-08-05 (developer feedback after actually using the wizard): the intro/welcome
// screen no longer validates or shows anything about the file's own content - not even an
// unknown e-mail - since resolving that is what steps 2-3 exist for (see
// plans/working_schedule_import_redesign.md). "Continue" only ever depends on a file being
// attached at all, so an unknown e-mail here doesn't block leaving the intro screen any more;
// it only surfaces once the flow reaches the real "Import" click at the final step (today, since
// steps 2-6 are still placeholders) - as a plain error dialog, the same way any other
// ValidationError from a button action renders.
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
            trigger: ".modal .modal-footer button[name='action_continue']:not([disabled])",
            content: "Continue is enabled purely because a file is attached - the unknown e-mail inside it isn't checked at this screen any more",
            run: "click",
        },
        {
            trigger: ".modal .alert-success:contains('Every group mentioned in the file was recognized')",
            content: "The 'groups' screen shows the success message - this file has no '<Students>' at all",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'groups' step (nothing to resolve here)",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'teachers' placeholder step",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'internal_conflicts' placeholder step",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'db_conflicts' placeholder step",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'pending_info' placeholder step",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='import_planner_data']:not([disabled])",
            content: "Click 'Import' - only now does the unknown e-mail actually get looked up",
            run: "click",
        },
        {
            trigger: ".o_error_dialog:contains('unknown.tour.teacher@example.com')",
            content: "The unknown e-mail surfaces as a real error dialog at Import time, not earlier",
        },
    ],
});

// A code with no '@' (e.g. "X1") is NOT a real e-mail typo - it's the external planner's way
// of naming a not-yet-staffed post. This must NOT block the import: importing creates a
// pending-identification teacher whose schedule is assigned immediately. This tour proves the
// full multi-step flow and the new "Pending identification" indicator actually render in the
// browser - a TransactionCase proves the model/importer logic works, but not that the view
// (badge column, ribbon) doesn't crash or silently fail to show. Since 2026-08-05, the intro
// screen no longer shows a banner for this at all (see the unknown-teacher tour above for the
// full rationale) - the two placeholder-code teachers below are simply cached silently and only
// actually get created once the flow reaches the real Import click.
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
            // Two teacher nodes with no '@' anywhere in their 'name' attribute: a short placeholder
            // code ("TOURX1", no discardable label after it) and a not-yet-hired teacher's own real,
            // multi-word name ("Tour Fulano Pending") - reported 2026-08-01: naively splitting on the
            // first space truncated the latter down to just "Tour". Both must be listed whole, each as
            // its own bullet, not collapsed into one comma sentence.
            trigger: ".modal .o_field_widget[name='attachment_ids']",
            content: "Import wizard dialog opened",
            run: async () => {
                const xml = '<root>'
                    + '<T name="TOURX1"><D name="1 Monday"><H name="1 09:00">'
                    + '<NonTeaching name="G Guard"/></H></D></T>'
                    + '<T name="Tour Fulano Pending"><D name="1 Monday"><H name="1 09:00">'
                    + '<NonTeaching name="G Guard"/></H></D></T>'
                    + '</root>';
                const file = new File([xml], "planner_pending.xml", { type: "text/xml" });
                await inputFiles(".modal .o_field_widget[name='attachment_ids'] .o_input_file", [file]);
            },
        },
        {
            trigger: ".modal .o_field_widget[name='attachment_ids'] .o_attachment",
            content: "File attached",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']:not([disabled])",
            content: "Continue is enabled purely because a file is attached - leaving the intro screen parses and caches both placeholder-code teachers (nothing written yet)",
            run: "click",
        },
        // Steps 'teachers' through 'pending_info' have no screen of their own yet (see
        // plans/working_schedule_import_redesign.md) - each is a placeholder "Continue" click
        // that just advances the statusbar. Not asserting on the statusbar's own DOM here (its
        // items can fold into a "more" dropdown under narrow viewports, purely width-driven -
        // see web.StatusBarField's adjustVisibleItems - which would make a `data-value=...`
        // selector flaky); the "Import" button only appearing once every placeholder has been
        // clicked through is itself the proof the skeleton advances correctly end-to-end. 'groups'
        // (just above) is the other real step built so far - see the tour dedicated to it,
        // 'ems_working_schedules_import_resolve_group', below.
        {
            trigger: ".modal .alert-success:contains('Every group mentioned in the file was recognized')",
            content: "The 'groups' screen shows the success message - this file has no '<Students>' at all",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'groups' step (nothing to resolve here)",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'teachers' placeholder step",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'internal_conflicts' placeholder step",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'db_conflicts' placeholder step",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'pending_info' placeholder step",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='import_planner_data']:not([disabled])",
            content: "The final step's 'Import' button appeared - click it. Only now does anything actually get written",
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

// Screen 2 ("Resolve groups", 2026-08-05, see plans/working_schedule_import_redesign.md's step 2)
// - an unresolved '<Students>' name no longer blocks the intro screen: it now surfaces here as an
// editable list row (raw name + a Many2one to pick the real group), and picking one applies to
// every occurrence of that name across the whole batch. This tour proves that new screen actually
// renders and resolves in a real browser (a TransactionCase already proves the underlying model
// logic - see TestWorkingSchedulesImportWizard.
// test_continue_from_groups_resolves_pending_group_and_completes_import). The real group ("Tour
// Resolve Group") is seeded by the Python test method; the XML deliberately names something else
// ("TourUnresolvedGroupXYZ Group") so none of '_resolve_group_name's heuristics match it at parse
// time. The teacher is a placeholder code (no '@'), not a real e-mail, so Import can succeed
// without needing an existing teacher fixture too - same pattern as the pending-teacher tour above.
registry.category("web_tour.tours").add("ems_working_schedules_import_resolve_group", {
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
                const xml = '<root><T name="TOURGROUPTEACHER"><D name="1 Monday"><H name="1 09:00">'
                    + '<Subject name="TOURRESOLVEGROUP Tour Resolve Group Subject"/>'
                    + '<Students name="TourUnresolvedGroupXYZ Group"/>'
                    + '</H></D></T></root>';
                const file = new File([xml], "planner_resolve_group.xml", { type: "text/xml" });
                await inputFiles(".modal .o_field_widget[name='attachment_ids'] .o_input_file", [file]);
            },
        },
        {
            trigger: ".modal .o_field_widget[name='attachment_ids'] .o_attachment",
            content: "File attached",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']:not([disabled])",
            content: "Continue is enabled purely because a file is attached",
            run: "click",
        },
        {
            trigger: ".modal .o_data_cell:contains('TourUnresolvedGroupXYZ Group')",
            content: "The 'groups' screen lists the unresolved raw name found in the file",
        },
        {
            // Continue renders as a disabled (grayed-out) twin while a line is still unresolved,
            // rather than disappearing (developer feedback 2026-08-05: "que quedará mas claro si
            // los botones de continuar... aparecen como enabled o disabled") - it stays in the
            // same spot, just not clickable, until every row has a group picked.
            trigger: ".modal .modal-footer button[name='action_continue_disabled'][disabled]",
            content: "Continue shows disabled - the group hasn't been picked yet",
        },
        {
            trigger: ".modal .o_data_row .o_data_cell[name='group_id']",
            content: "Click the row's group cell to edit it",
            run: "click",
        },
        {
            trigger: ".modal .o_selected_row .o_field_widget[name='group_id'] input",
            content: "Search for the seeded group",
            run: "edit Tour Resolve Group",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Tour Resolve Group')",
            content: "Select it",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']:not([disabled])",
            content: "Continue is enabled now that the group is picked - the picked group resolves every occurrence of the raw name",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'teachers' placeholder step",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'internal_conflicts' placeholder step",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'db_conflicts' placeholder step",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'pending_info' placeholder step",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='import_planner_data']:not([disabled])",
            content: "Click 'Import' - the resolved group is what actually gets written",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal)) .o_list_view",
            content: "Back to the Working Schedules list, confirming the resolved-group import completed",
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
