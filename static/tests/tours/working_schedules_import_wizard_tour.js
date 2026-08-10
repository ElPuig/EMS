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
// attached at all, so an unknown e-mail here doesn't block leaving the intro screen any more.
//
// Updated again 2026-08-05, once screen 3 ("Resolve teachers") was actually built: an unknown
// e-mail no longer reaches Import at all - it surfaces right here, as an unresolved line on the
// 'teachers' screen, with "Continue" rendering disabled (not hidden - see 'continue_disabled')
// until a real teacher is picked for it. This tour proves it stays blocked when left unresolved;
// see 'ems_working_schedules_import_resolve_teacher_email' below for the full resolve-and-complete
// path (mirroring 'ems_working_schedules_import_resolve_group').
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
            trigger: ".modal .o_data_cell:contains('unknown.tour.teacher@example.com')",
            content: "The 'teachers' screen lists the unresolved e-mail found in the file",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']:not([disabled])",
            content: "Continue shows enabled by default - 'New' defaults to ticked (2026-08-06)",
        },
        {
            // A boolean cell's FIRST click both enters row-edit mode AND toggles the value in one
            // go - a single click here unticks the default-True 'New'.
            trigger: ".modal .o_data_row .o_data_cell[name='create_new']",
            content: "Untick 'New' to leave the row genuinely unresolved, on purpose, for this tour",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue_disabled'][disabled]",
            content: "Continue shows disabled now that neither a teacher nor 'New' is set",
        },
        {
            // Cancel (discard) rather than leaving the tour mid-edit - the row is still in
            // edition after unticking 'New' (a plain click elsewhere doesn't reliably blur/save
            // an x2many list row), and ending a tour with an open, unsaved form view fails at
            // teardown ("Tour finished with an open form view in edition mode").
            trigger: ".modal .modal-footer button:contains('Cancel')",
            content: "Cancel - this tour only needs to prove Continue stays blocked, not complete the import",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal)) .o_list_view",
            content: "Back to the Working Schedules list, dialog closed cleanly",
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
        // 'groups', 'teachers', 'internal_conflicts' and 'db_conflicts' (just below) are the other
        // real steps built so far - neither placeholder code here is e-mail-shaped, so 'teachers'
        // has nothing to resolve; both teachers' entries are NonTeaching (no classroom to collide
        // over), so neither conflicts screen has anything to resolve either - all show their own
        // success message. See the tours dedicated to each, 'ems_working_schedules_import_
        // resolve_group'/'ems_working_schedules_import_resolve_teacher_email'/
        // 'ems_working_schedules_import_resolve_internal_conflict'/'ems_working_schedules_import_
        // resolve_db_conflict', below.
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
            trigger: ".modal .alert-success:contains('Every teacher e-mail mentioned in the file was recognized')",
            content: "The 'teachers' screen shows its own success message - neither placeholder code is e-mail-shaped",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'teachers' step (nothing to resolve here)",
            run: "click",
        },
        {
            // Screen 6 ("Pending teachers", 2026-08-10, moved right after 'teachers' the same day -
            // see docs/en/developers/employees/working_schedule.md's own section) - both teachers
            // here are placeholder codes/never-e-mail-shaped, so both must be listed as about to
            // become new pending-identification employees. A short code renders whole ("TOURX1"); a
            // not-yet-hired teacher's own real, multi-word name must too (see the earlier bug this
            // same fixture already exercises for the 'teachers' screen).
            trigger: ".modal .o_field_widget[name='pending_teachers_html'] li:contains('TOURX1')",
            content: "The short placeholder code is listed as a pending teacher to be created",
        },
        {
            trigger: ".modal .o_field_widget[name='pending_teachers_html'] li:contains('Tour Fulano Pending')",
            content: "The multi-word placeholder name is listed whole, not truncated",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'pending_info' step",
            run: "click",
        },
        {
            trigger: ".modal .alert-success:contains('No room conflicts were found within this batch')",
            content: "The 'internal_conflicts' screen shows its own success message - both teachers' entries here are NonTeaching, which carries no classroom to collide over",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'internal_conflicts' step (nothing to resolve here)",
            run: "click",
        },
        {
            trigger: ".modal .alert-success:contains('No conflicts were found against already-active schedules')",
            content: "The 'db_conflicts' screen shows its own success message - no pre-existing session collides here",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'db_conflicts' step (nothing to resolve here)",
            run: "click",
        },
        {
            // "Overall summary" - neither teacher here already exists, so the "existing
            // teacher(s) affected" block shows its own empty placeholder instead of a list.
            trigger: ".modal .o_field_widget[name='overall_summary_html']:contains('0 existing teacher(s) affected')",
            content: "The 'summary' screen's own block confirms neither teacher here already exists",
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
            trigger: ".modal .alert-success:contains('Every teacher e-mail mentioned in the file was recognized')",
            content: "The 'teachers' screen shows its own success message - the teacher here is a placeholder code, not an e-mail",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'teachers' step (nothing to resolve here)",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'pending_info' step",
            run: "click",
        },
        {
            trigger: ".modal .alert-success:contains('No room conflicts were found within this batch')",
            content: "The 'internal_conflicts' screen shows its own success message - only one teacher is in this batch, so no collision is possible",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'internal_conflicts' step (nothing to resolve here)",
            run: "click",
        },
        {
            trigger: ".modal .alert-success:contains('No conflicts were found against already-active schedules')",
            content: "The 'db_conflicts' screen shows its own success message - no pre-existing session collides here",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'db_conflicts' step (nothing to resolve here)",
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

// Screen 3 ("Resolve teachers", 2026-08-05, see plans/working_schedule_import_redesign.md's step
// 3) - an unresolved e-mail no longer reaches Import at all: it surfaces here as an editable list
// row (raw e-mail + a Many2one to pick the real teacher, create disabled - a brand-new teacher is
// screen 6's job, not this one's). Mirrors 'ems_working_schedules_import_resolve_group' exactly.
// The real teacher ("Tour Resolve Teacher Email") is seeded by the Python test method; the XML
// deliberately uses a different, unknown e-mail so a 'teacher_line' is actually created.
registry.category("web_tour.tours").add("ems_working_schedules_import_resolve_teacher_email", {
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
                const xml = '<root><T name="tour.unresolved.teacher@example.com Someone">'
                    + '<D name="1 Monday"><H name="1 09:00"><NonTeaching name="G Guard"/></H></D>'
                    + '</T></root>';
                const file = new File([xml], "planner_resolve_teacher.xml", { type: "text/xml" });
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
            trigger: ".modal .alert-success:contains('Every group mentioned in the file was recognized')",
            content: "The 'groups' screen shows the success message - this file has no '<Students>' at all",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'groups' step (nothing to resolve here)",
            run: "click",
        },
        {
            trigger: ".modal .o_data_cell:contains('tour.unresolved.teacher@example.com')",
            content: "The 'teachers' screen lists the unresolved e-mail found in the file",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']:not([disabled])",
            content: "Continue shows enabled by default - 'New' defaults to ticked (2026-08-06)",
        },
        {
            // A boolean cell's FIRST click both enters row-edit mode AND toggles the value in one
            // go - a single click here unticks the default-True 'New', which is also what unlocks
            // the 'employee_id' selector (readonly="create_new" in the view).
            trigger: ".modal .o_data_row .o_data_cell[name='create_new']",
            content: "Untick 'New' - this is really a typo/mismatch of an existing teacher",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue_disabled'][disabled]",
            content: "Continue shows disabled again - the teacher hasn't been picked yet",
        },
        {
            trigger: ".modal .o_data_row .o_data_cell[name='employee_id']",
            content: "Click the row's teacher cell to edit it",
            run: "click",
        },
        {
            trigger: ".modal .o_selected_row .o_field_widget[name='employee_id'] input",
            content: "Search for the seeded teacher",
            run: "edit Tour Resolve Teacher Email",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Tour Resolve Teacher Email')",
            content: "Select it",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']:not([disabled])",
            content: "Continue is enabled now that the teacher is picked - the picked teacher resolves every occurrence of the e-mail",
            run: "click",
        },
        {
            trigger: ".modal .alert-success:contains('No new teacher will be created')",
            content: "The 'pending_info' screen shows its own success message - the one teacher here already exists",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'pending_info' step",
            run: "click",
        },
        {
            trigger: ".modal .alert-success:contains('No room conflicts were found within this batch')",
            content: "The 'internal_conflicts' screen shows its own success message - only one teacher is in this batch, so no collision is possible",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'internal_conflicts' step (nothing to resolve here)",
            run: "click",
        },
        {
            trigger: ".modal .alert-success:contains('No conflicts were found against already-active schedules')",
            content: "The 'db_conflicts' screen shows its own success message - no pre-existing session collides here",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'db_conflicts' step (nothing to resolve here)",
            run: "click",
        },
        {
            // "Overall summary" - the teacher resolved on the 'teachers' step is exactly the
            // kind of item the "existing teacher(s) affected" block previews.
            trigger: ".modal .o_field_widget[name='overall_summary_html'] li:contains('Tour Resolve Teacher Email')",
            content: "The resolved teacher is listed as an existing teacher whose schedule is about to be recreated",
        },
        {
            trigger: ".modal .modal-footer button[name='import_planner_data']:not([disabled])",
            content: "Click 'Import' - the resolved teacher is what actually gets written",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal)) .o_list_view",
            content: "Back to the Working Schedules list, confirming the resolved-teacher import completed",
        },
    ],
});

// Screen 3, "Create new" checkbox (2026-08-05, developer feedback after using the wizard for
// real) - some unresolved e-mails belong to a genuinely never-hired teacher, not a typo/mismatch
// of an existing one. Ticking "Create new" locks (readonly) the row's 'employee_id' selector -
// this tour proves that lock actually renders in a real browser, not just at the model level
// (readonly="create_new" is arch-valid but says nothing about whether it visually takes effect) -
// then completes the import and confirms the resulting pending teacher in the list view, mirroring
// 'ems_working_schedules_import_pending_teacher's own final assertion for a placeholder code.
registry.category("web_tour.tours").add("ems_working_schedules_import_create_new_teacher", {
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
                const xml = '<root><T name="tour.create.new.teacher@example.com Someone">'
                    + '<D name="1 Monday"><H name="1 09:00"><NonTeaching name="G Guard"/></H></D>'
                    + '</T></root>';
                const file = new File([xml], "planner_create_new_teacher.xml", { type: "text/xml" });
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
            trigger: ".modal .alert-success:contains('Every group mentioned in the file was recognized')",
            content: "The 'groups' screen shows the success message - this file has no '<Students>' at all",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'groups' step (nothing to resolve here)",
            run: "click",
        },
        {
            trigger: ".modal .o_data_cell:contains('tour.create.new.teacher@example.com')",
            content: "The 'teachers' screen lists the unresolved e-mail found in the file",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']:not([disabled])",
            content: "Continue shows enabled by default - 'New' defaults to ticked (2026-08-06)",
        },
        {
            trigger: ".modal .o_data_row .o_data_cell[name='employee_id'].o_readonly_modifier",
            content: "The teacher selector is already locked (readonly) by default, matching 'readonly=\"create_new\"' in the view - 'New' starts ticked, nothing to click here",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']:not([disabled])",
            content: "Continue is enabled purely from 'New' being ticked, with no teacher picked",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'pending_info' step",
            run: "click",
        },
        {
            trigger: ".modal .alert-success:contains('No room conflicts were found within this batch')",
            content: "The 'internal_conflicts' screen shows its own success message - only one teacher is in this batch, so no collision is possible",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'internal_conflicts' step (nothing to resolve here)",
            run: "click",
        },
        {
            trigger: ".modal .alert-success:contains('No conflicts were found against already-active schedules')",
            content: "The 'db_conflicts' screen shows its own success message - no pre-existing session collides here",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'db_conflicts' step (nothing to resolve here)",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='import_planner_data']:not([disabled])",
            content: "Click 'Import' - a brand-new pending-identification teacher gets created",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal)) .o_list_view",
            content: "Back to the Working Schedules list, confirming the create-new import completed",
        },
    ],
});

// Screen 4 ("Internal conflicts", 2026-08-05, see plans/working_schedule_import_redesign.md's
// step 4) - two DIFFERENT teachers in the same batch, same subject, DIFFERENT groups sharing the
// SAME classroom at the same slot: a "desdoble" (split session) needing two different rooms. This
// tour proves the room-reassignment path renders and resolves in a real browser - both teachers
// are already-known e-mails (no group/teacher line needed), so this exercises 'internal_conflicts'
// in isolation. "Continue" stays disabled while both rooms are still the same (the pre-filled
// default), same as picking no group/teacher would on the earlier screens.
registry.category("web_tour.tours").add("ems_working_schedules_import_resolve_internal_conflict", {
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
                const xml = '<root>'
                    + '<T name="tour.resolve.conflict.a@example.com Someone"><D name="1 Monday"><H name="1 09:00">'
                    + '<Subject name="TOURRESOLVECONFLICT Tour Resolve Conflict Subject"/>'
                    + '<Students name="Tour Resolve Conflict Group A"/>'
                    + '</H></D></T>'
                    + '<T name="tour.resolve.conflict.b@example.com Someone Else"><D name="1 Monday"><H name="1 09:00">'
                    + '<Subject name="TOURRESOLVECONFLICT Tour Resolve Conflict Subject"/>'
                    + '<Students name="Tour Resolve Conflict Group B"/>'
                    + '</H></D></T>'
                    + '</root>';
                const file = new File([xml], "planner_resolve_conflict.xml", { type: "text/xml" });
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
            trigger: ".modal .alert-success:contains('Every group mentioned in the file was recognized')",
            content: "Both seeded groups are recognized by exact name",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'groups' step (nothing to resolve here)",
            run: "click",
        },
        {
            trigger: ".modal .alert-success:contains('Every teacher e-mail mentioned in the file was recognized')",
            content: "Both seeded teachers are recognized by e-mail",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'teachers' step (nothing to resolve here)",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'pending_info' step",
            run: "click",
        },
        {
            trigger: ".modal .o_data_cell:contains('Tour Resolve Conflict Group A')",
            content: "The 'internal_conflicts' screen lists the colliding pair (same subject, different groups sharing a room)",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue_disabled'][disabled]",
            content: "Continue shows disabled - both rooms still default to the same colliding classroom",
        },
        {
            trigger: ".modal .o_data_row .o_data_cell[name='right_space_id']",
            content: "Click the row's right classroom cell to edit it",
            run: "click",
        },
        {
            trigger: ".modal .o_selected_row .o_field_widget[name='right_space_id'] input",
            content: "Search for the seeded second classroom",
            run: "edit Tour Resolve Conflict Space B",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Tour Resolve Conflict Space B')",
            content: "Select it - the two rooms now differ, actually resolving the collision",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']:not([disabled])",
            content: "Continue is enabled now that the two rooms differ",
            run: "click",
        },
        {
            trigger: ".modal .alert-success:contains('No conflicts were found against already-active schedules')",
            content: "The 'db_conflicts' screen shows its own success message - no pre-existing session collides here",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'db_conflicts' step (nothing to resolve here)",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='import_planner_data']:not([disabled])",
            content: "Click 'Import' - each group's session gets its own resolved room",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal)) .o_list_view",
            content: "Back to the Working Schedules list, confirming the resolved-conflict import completed",
        },
    ],
});

// Screen 5 ("Existing schedule conflicts", 2026-08-05, see plans/working_schedule_import_
// redesign.md's step 5) - same classification/resolution shape as screen 4, but the right side is
// a real, already-active 'ems.attendance_schedule' DB record instead of another entry from this
// same batch. The Python test method seeds that existing session directly via the ORM (a teacher
// already has an active class in "Tour Resolve DB Conflict Space A"); this tour imports a
// SECOND, different teacher into the sibling group sharing that same room - a "desdoble" needing
// a room reassignment, exactly like the internal-conflict tour above, just against a real DB
// session rather than another entry in the same file.
registry.category("web_tour.tours").add("ems_working_schedules_import_resolve_db_conflict", {
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
                const xml = '<root><T name="tour.resolve.dbconflict.b@example.com Someone Else">'
                    + '<D name="1 Monday"><H name="1 09:00">'
                    + '<Subject name="TOURRESOLVEDBCONFLICT Tour Resolve DB Conflict Subject"/>'
                    + '<Students name="Tour Resolve DB Conflict Group B"/>'
                    + '</H></D></T></root>';
                const file = new File([xml], "planner_resolve_db_conflict.xml", { type: "text/xml" });
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
            trigger: ".modal .alert-success:contains('Every group mentioned in the file was recognized')",
            content: "The seeded group is recognized by exact name",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'groups' step (nothing to resolve here)",
            run: "click",
        },
        {
            trigger: ".modal .alert-success:contains('Every teacher e-mail mentioned in the file was recognized')",
            content: "The seeded teacher is recognized by e-mail",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'teachers' step (nothing to resolve here)",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'pending_info' step",
            run: "click",
        },
        {
            trigger: ".modal .alert-success:contains('No room conflicts were found within this batch')",
            content: "Only one teacher is in THIS batch, so no within-batch collision is possible",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'internal_conflicts' step (nothing to resolve here)",
            run: "click",
        },
        {
            trigger: ".modal .o_data_cell:contains('Tour Resolve DB Conflict Group B')",
            content: "The 'db_conflicts' screen lists the collision against the already-active DB session",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue_disabled'][disabled]",
            content: "Continue shows disabled - both rooms still default to the same colliding classroom",
        },
        {
            trigger: ".modal .o_data_row .o_data_cell[name='right_space_id']",
            content: "Click the row's right classroom cell to edit it",
            run: "click",
        },
        {
            trigger: ".modal .o_selected_row .o_field_widget[name='right_space_id'] input",
            content: "Search for the seeded second classroom",
            run: "edit Tour Resolve DB Conflict Space B",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Tour Resolve DB Conflict Space B')",
            content: "Select it - the two rooms now differ, actually resolving the collision",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']:not([disabled])",
            content: "Continue is enabled now that the two rooms differ",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='import_planner_data']:not([disabled])",
            content: "Click 'Import' - the new entry's room and the existing session's own new room both get written",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal)) .o_list_view",
            content: "Back to the Working Schedules list, confirming the resolved-db-conflict import completed",
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
