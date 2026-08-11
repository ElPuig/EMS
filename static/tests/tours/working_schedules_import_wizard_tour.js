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
            trigger: ".modal .alert-success:contains('Every subject matches its group')",
            content: "The 'subjects' screen shows the success message - no mismatch in this fixture",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'subjects' step (nothing to resolve here)",
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
// full rationale). Since 2026-08-10 (the "Pending teachers" screen merged into "Resolve
// teachers" - see docs/en/developers/employees/working_schedule.md), a bare placeholder code is
// no longer cached silently: it surfaces right on the 'teachers' screen as its own correction
// row, exactly like an unresolved e-mail, with 'create_new' already ticked by default - nothing
// to click there, but the row must be visible.
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
        // real steps built so far - both teachers' entries are NonTeaching (no classroom to
        // collide over), so neither conflicts screen has anything to resolve - both show their own
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
            trigger: ".modal .alert-success:contains('Every subject matches its group')",
            content: "The 'subjects' screen shows the success message - no mismatch in this fixture",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'subjects' step (nothing to resolve here)",
            run: "click",
        },
        {
            // Both placeholder codes are listed here as their own correction row (merged from the
            // former, separate "Pending teachers" preview screen, 2026-08-10 - see docs/en/
            // developers/employees/working_schedule.md). A short code renders whole ("TOURX1"); a
            // not-yet-hired teacher's own real, multi-word name must too (the same truncation bug
            // this fixture already exercises for a real e-mail elsewhere in this file).
            trigger: ".modal .o_data_cell:contains('TOURX1')",
            content: "The short placeholder code is listed as its own unresolved row",
        },
        {
            trigger: ".modal .o_data_cell:contains('Tour Fulano Pending')",
            content: "The multi-word placeholder name is listed whole, not truncated",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']:not([disabled])",
            content: "Continue through the 'teachers' step - 'create_new' already defaults to True for both rows, nothing to click",
            run: "click",
        },
        {
            trigger: ".modal .alert-success:contains('No conflicts were found within this batch')",
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
            trigger: ".modal .alert-success:contains('Every subject matches its group')",
            content: "The 'subjects' screen shows the success message - the resolved group is a reinforcement type with no study, so nothing to check",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'subjects' step (nothing to resolve here)",
            run: "click",
        },
        {
            trigger: ".modal .o_data_cell:contains('TOURGROUPTEACHER')",
            content: "The 'teachers' screen lists the placeholder code as its own unresolved row too (2026-08-10 merge)",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']:not([disabled])",
            content: "Continue through the 'teachers' step - 'create_new' already defaults to True, nothing to click",
            run: "click",
        },
        {
            trigger: ".modal .alert-success:contains('No conflicts were found within this batch')",
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

// "Resolve subjects" screen (2026-08-11, developer feedback after hitting a real error: "The
// subject '...' is not available in the following selected studies: ..."): a file subject code
// that resolves to a real 'ems.subject', but one not taught in the group's own study, now surfaces
// here instead of only as a confusing error at Import. Covers BOTH real variants (developer
// feedback the same day, after using the first version - group(s) shown read-only - for real:
// "Resolve subject debería dejarme cambiar también los grupos. Me he encontrado las dos variantes
// durante las pruebas: el error era el (o los) grupo, o el error era la asignatura"): teacher 1's
// row is fixed via the 'subject_id' Many2one dropdown (subject was wrong), teacher 2's row is
// fixed via the 'group_ids' many2many_tags widget (group was wrong, subject was fine all along) -
// proving both correction paths actually render and resolve in a real browser.
registry.category("web_tour.tours").add("ems_working_schedules_import_resolve_subject_mismatch", {
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
                    + '<T name="tour.subject.mismatch@example.com Someone">'
                    + '<D name="1 Monday"><H name="1 09:00">'
                    + '<Subject name="TOURSUBJWRONG Tour Subject Wrong"/>'
                    + '<Students name="TSUBJ1A"/>'
                    + '</H></D></T>'
                    + '<T name="tour.subject.mismatch.2@example.com Someone Else">'
                    + '<D name="1 Monday"><H name="1 09:00">'
                    + '<Subject name="TOURSUBJCORRECT Tour Subject Correct"/>'
                    + '<Students name="TSUBJW1A"/>'
                    + '</H></D></T></root>';
                const file = new File([xml], "planner_subject_mismatch.xml", { type: "text/xml" });
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
            content: "Both group names (TSUBJ1A, TSUBJW1A) are recognized by exact name",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'groups' step (nothing to resolve here)",
            run: "click",
        },
        {
            trigger: ".modal .o_data_cell:contains('Tour Subject Wrong')",
            content: "The 'subjects' screen lists the first mismatch: the file's own (wrong) subject, shown as the row's current value",
        },
        {
            trigger: ".modal .o_data_row:has(td:contains('TSUBJW1A'))",
            content: "The second mismatch also renders - a correct subject assigned to the wrong group",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue_disabled'][disabled]",
            content: "Continue shows disabled - both mismatches are still unresolved",
        },
        {
            trigger: ".modal .o_data_row:has(td:contains('TSUBJ1A')) .o_data_cell[name='subject_id']",
            content: "Click the first row's subject cell to edit it",
            run: "click",
        },
        {
            trigger: ".modal .o_selected_row .o_field_widget[name='subject_id'] input",
            content: "Search for the correct subject",
            run: "edit Tour Subject Correct",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Tour Subject Correct')",
            content: "Select it - proves the domain actually offers a subject valid for this group's own study",
            run: "click",
        },
        {
            trigger: ".modal .o_data_row:has(td:contains('TSUBJW1A')) .o_data_cell[name='group_ids']",
            content: "Click the second row's group cell to edit it",
            run: "click",
        },
        {
            trigger: ".modal .o_selected_row .o_field_widget[name='group_ids'] .o_tag:has(.o_tag_badge_text:contains('TSUBJW1A')) .o_delete",
            content: "Remove the wrong group tag",
            run: "click",
        },
        {
            trigger: ".modal .o_selected_row .o_field_widget[name='group_ids'] input",
            content: "Search for the correct group",
            run: "edit TSUBJ2A",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('TSUBJ2A')",
            content: "Select it - the group correction alone resolves this row, since the subject was already valid for it",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']:not([disabled])",
            content: "Continue is enabled now that both mismatches are resolved",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']:not([disabled])",
            content: "Continue through the 'teachers' step - both seeded teachers already match by e-mail, nothing to resolve",
            run: "click",
        },
        {
            trigger: ".modal .alert-success:contains('No conflicts were found within this batch')",
            content: "The 'internal_conflicts' screen shows its own success message - only one teacher is in this batch",
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
            content: "Click 'Import' - the corrected subject is what actually gets written",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal)) .o_list_view",
            content: "Back to the Working Schedules list, confirming the corrected-subject import completed",
        },
    ],
});

// Screen 3 ("Resolve teachers", 2026-08-05, see plans/working_schedule_import_redesign.md's step
// 3) - an unresolved e-mail no longer reaches Import at all: it surfaces here as an editable list
// row (raw e-mail + a Many2one to pick the real teacher, create disabled - ticking 'create_new'
// on this SAME row, not a separate screen, is what creates a brand-new pending teacher since the
// 2026-08-10 merge - see 'ems_working_schedules_import_create_new_teacher' below). Mirrors
// 'ems_working_schedules_import_resolve_group' exactly.
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
            trigger: ".modal .alert-success:contains('Every subject matches its group')",
            content: "The 'subjects' screen shows the success message - no mismatch in this fixture",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'subjects' step (nothing to resolve here)",
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
            trigger: ".modal .alert-success:contains('No conflicts were found within this batch')",
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
            trigger: ".modal .alert-success:contains('Every subject matches its group')",
            content: "The 'subjects' screen shows the success message - no mismatch in this fixture",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'subjects' step (nothing to resolve here)",
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
            trigger: ".modal .alert-success:contains('No conflicts were found within this batch')",
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
            trigger: ".modal .alert-success:contains('Every subject matches its group')",
            content: "The 'subjects' screen shows the success message - no mismatch in this fixture",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'subjects' step (nothing to resolve here)",
            run: "click",
        },
        {
            trigger: ".modal .alert-success:contains('Every teacher mentioned in the file was recognized')",
            content: "Both seeded teachers are recognized by e-mail",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'teachers' step (nothing to resolve here)",
            run: "click",
        },
        {
            trigger: ".modal .card:contains('Split session')",
            content: "The 'internal_conflicts' screen groups the colliding pair under its own 'Split session' card",
        },
        {
            trigger: ".modal .ems_conflict_row:contains('Tour Resolve Conflict Group B')",
            content: "The collision itself is listed as a row under the 'Tour Resolve Conflict Teacher A' sub-group",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue_disabled'][disabled]",
            content: "Continue shows disabled - both rooms still default to the same colliding classroom",
        },
        {
            trigger: ".modal .ems_conflict_row:contains('Tour Resolve Conflict Group B') .ems_conflict_space_right input",
            content: "Search for the seeded second classroom in the row's own right room picker",
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

// Screen 4's own 'self_conflict' kind (2026-08-10, developer feedback against a real import) -
// two DIFFERENT placeholder codes, both manually assigned (on the 'teachers' screen) to the SAME
// already-existing employee, whose own two sessions collide in weekday/time but NOT in room -
// exactly the shape no room-based check can ever catch. This tour proves the row actually renders
// (with its own "Same teacher, different room" label and only Left/Right prevails offered, no
// "Confirm"/"Reassign rooms") and resolves in a real browser.
registry.category("web_tour.tours").add("ems_working_schedules_import_resolve_self_conflict", {
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
                    + '<T name="TOURSELFX1"><D name="1 Monday"><H name="1 09:00">'
                    + '<Subject name="TOURSELFCONFLICT Tour Self Conflict Subject"/>'
                    + '<Students name="Tour Self Conflict Group A"/>'
                    + '</H></D></T>'
                    + '<T name="TOURSELFX2"><D name="1 Monday"><H name="1 09:00">'
                    + '<Subject name="TOURSELFCONFLICT Tour Self Conflict Subject"/>'
                    + '<Students name="Tour Self Conflict Group B"/>'
                    + '</H></D></T>'
                    + '</root>';
                const file = new File([xml], "planner_resolve_self_conflict.xml", { type: "text/xml" });
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
            trigger: ".modal .alert-success:contains('Every subject matches its group')",
            content: "The 'subjects' screen shows the success message - no mismatch in this fixture",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'subjects' step (nothing to resolve here)",
            run: "click",
        },
        {
            trigger: ".modal .o_data_cell:contains('TOURSELFX1')",
            content: "The 'teachers' screen lists both unresolved placeholder codes",
        },
        {
            // A boolean cell's FIRST click both enters row-edit mode AND toggles the value in one
            // go - a single click here unticks the default-True 'New' on the first row.
            trigger: ".modal .o_data_row:has(.o_data_cell:contains('TOURSELFX1')) .o_data_cell[name='create_new']",
            content: "Untick 'New' on the first row - this is the already-existing teacher",
            run: "click",
        },
        {
            trigger: ".modal .o_data_row:has(.o_data_cell:contains('TOURSELFX1')) .o_data_cell[name='employee_id']",
            content: "Click the row's teacher cell to edit it",
            run: "click",
        },
        {
            trigger: ".modal .o_selected_row .o_field_widget[name='employee_id'] input",
            content: "Search for the seeded teacher",
            run: "edit Tour Self Conflict Teacher",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Tour Self Conflict Teacher')",
            content: "Select it for the first identifier",
            run: "click",
        },
        {
            trigger: ".modal .o_data_row:has(.o_data_cell:contains('TOURSELFX2')) .o_data_cell[name='create_new']",
            content: "Untick 'New' on the second row too - the SAME real person, sent under a different code",
            run: "click",
        },
        {
            trigger: ".modal .o_data_row:has(.o_data_cell:contains('TOURSELFX2')) .o_data_cell[name='employee_id']",
            content: "Click the row's teacher cell to edit it",
            run: "click",
        },
        {
            trigger: ".modal .o_selected_row .o_field_widget[name='employee_id'] input",
            content: "Search for the same seeded teacher",
            run: "edit Tour Self Conflict Teacher",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Tour Self Conflict Teacher')",
            content: "Select it for the second identifier too - both now resolve to the same employee",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']:not([disabled])",
            content: "Continue is enabled now that both rows have a teacher picked",
            run: "click",
        },
        {
            trigger: ".modal .card-header:contains('Same teacher, different room')",
            content: "The 'internal_conflicts' screen lists the self-conflict, correctly classified even though the two rooms genuinely differ",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']:not([disabled])",
            content: "Continue is already enabled - 'Left prevails' is a valid default for this kind",
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
            content: "Click 'Import' - only the left (Group A) session survives for this teacher",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal)) .o_list_view",
            content: "Back to the Working Schedules list, confirming the resolved self-conflict import completed",
        },
    ],
});

// The grouped-cards widget's own bulk-resolution dropdown (2026-08-10, developer feedback after
// resolving a large real batch by hand: "me iría bien que estuvieran agrupadas por tipo... y por
// 'left', y que cada grupo me permitiera escoger el resolution que se aplica al grupo entero").
// Three groups sharing the SAME classroom: the anchor's own entry collides (desdoble) with BOTH
// other entries at the exact same slot, forming a sub-group with TWO rows under it, plus a second,
// one-row sub-group for the remaining pair between those other two. This tour proves picking a
// value in a sub-group's own bulk selector actually resolves every row under it at once - "Continue"
// only ever enables once every row's own resolution is valid, so this is proven functionally
// (the same idiom every other tour in this file already uses), not by inspecting each row's
// dropdown value directly.
registry.category("web_tour.tours").add("ems_working_schedules_import_bulk_apply_resolution", {
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
                    + '<T name="TOURBULKX1"><D name="1 Monday"><H name="1 09:00">'
                    + '<Subject name="TOURBULKAPPLY Tour Bulk Apply Subject"/>'
                    + '<Students name="Tour Bulk Apply Group A"/>'
                    + '</H></D></T>'
                    + '<T name="TOURBULKX2"><D name="1 Monday"><H name="1 09:00">'
                    + '<Subject name="TOURBULKAPPLY Tour Bulk Apply Subject"/>'
                    + '<Students name="Tour Bulk Apply Group B"/>'
                    + '</H></D></T>'
                    + '<T name="TOURBULKX3"><D name="1 Monday"><H name="1 09:00">'
                    + '<Subject name="TOURBULKAPPLY Tour Bulk Apply Subject"/>'
                    + '<Students name="Tour Bulk Apply Group C"/>'
                    + '</H></D></T>'
                    + '</root>';
                const file = new File([xml], "planner_bulk_apply.xml", { type: "text/xml" });
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
            content: "All three seeded groups are recognized by exact name",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'groups' step (nothing to resolve here)",
            run: "click",
        },
        {
            trigger: ".modal .alert-success:contains('Every subject matches its group')",
            content: "The 'subjects' screen shows the success message - no mismatch in this fixture",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'subjects' step (nothing to resolve here)",
            run: "click",
        },
        {
            trigger: ".modal .o_data_cell:contains('TOURBULKX1')",
            content: "The 'teachers' screen lists all three unresolved placeholder codes",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']:not([disabled])",
            content: "Continue through the 'teachers' step - 'create_new' already defaults to True for every row",
            run: "click",
        },
        {
            trigger: ".modal .ems_conflict_subgroup:has(strong:contains('TOURBULKX1')) .ems_conflict_row",
            content: "The sub-group for the anchor entry (grouped by teacher+subject, TOURBULKX1) lists both of its own colliding pairs as rows",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue_disabled'][disabled]",
            content: "Continue shows disabled - every row still defaults to 'Reassign rooms' with both sides identical",
        },
        {
            trigger: ".modal .ems_conflict_subgroup:has(strong:contains('TOURBULKX1')) .ems_conflict_bulk_select",
            content: "Bulk-apply 'Left prevails' to BOTH rows under the TOURBULKX1 sub-group at once",
            run: "select prevail_left",
        },
        {
            trigger: ".modal .ems_conflict_subgroup:has(strong:contains('TOURBULKX2')) .ems_conflict_bulk_select",
            content: "Bulk-apply 'Left prevails' to the remaining sub-group's own single row too",
            run: "select prevail_left",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']:not([disabled])",
            content: "Continue is enabled now that every row (both bulk-applied at once) has a valid resolution",
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
            content: "Click 'Import' - only the anchor's (Group A) session survives for this slot/room",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal)) .o_list_view",
            content: "Back to the Working Schedules list, confirming the bulk-resolved import completed",
        },
    ],
});

// Proves the grouped-cards widget has no hidden record cap at all (developer feedback 2026-08-10,
// right after a hardcoded arch 'limit="1000"' fix: "si tuviéramos más de 1000 conflictos
// estaríamos en las mismas... ¿no se puede paginar, o de alguna otra forma?") - 85 colliding pairs
// (past Odoo's own x2many 'DEFAULT_LIMIT' of 80, the actual number silently truncating 'records'
// before the widget's 'setup()' started force-loading everything via 'list.load({ limit:
// list.count })') all land in ONE sub-group (same anchor teacher+subject), then a single bulk-
// apply resolves every one of them at once.
registry.category("web_tour.tours").add("ems_working_schedules_import_conflicts_beyond_default_page_size", {
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
                const nodes = [];
                for (let index = 0; index < 86; index++) {
                    nodes.push(
                        `<T name="TOURPAGEX${index}"><D name="1 Monday"><H name="1 09:00">`
                        + '<Subject name="TOURPAGINATION Tour Pagination Subject"/>'
                        + `<Students name="Tour Pagination Group ${index}"/>`
                        + '</H></D></T>'
                    );
                }
                const xml = `<root>${nodes.join("")}</root>`;
                const file = new File([xml], "planner_pagination.xml", { type: "text/xml" });
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
            content: "All 86 seeded groups are recognized by exact name",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'groups' step (nothing to resolve here)",
            run: "click",
        },
        {
            trigger: ".modal .alert-success:contains('Every subject matches its group')",
            content: "The 'subjects' screen shows the success message - no mismatch in this fixture",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'subjects' step (nothing to resolve here)",
            run: "click",
        },
        {
            trigger: ".modal .o_data_cell:contains('TOURPAGEX85')",
            content: "The 'teachers' screen lists every one of the 86 unresolved placeholder codes, including the last one",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']:not([disabled])",
            content: "Continue through the 'teachers' step - 'create_new' already defaults to True for every row",
            run: "click",
        },
        {
            trigger: ".modal .ems_conflict_subgroup:has(strong:contains('TOURPAGEX0')) .ems_conflict_row:contains('TOURPAGEX85')",
            content: "The single sub-group (anchor teacher+subject) actually renders its 85th colliding row, not just the first 80 - proves the widget's own full-count load, not a raised-but-still-finite arch limit",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue_disabled'][disabled]",
            content: "Continue shows disabled - 'continue_disabled' correctly considers all 85 rows, not a truncated subset (the actual, real-world symptom the developer originally hit: this computed field always saw every line, even while the OLD arch-limited widget could only ever RENDER the first 80 of them, leaving the rest unresolvable with no visible reason)",
        },
        // Deliberately stops here rather than also bulk-applying to all 85 rows and clicking
        // Continue: resolving a genuinely huge single sub-group is real, but SEPARATE, additional
        // work to prove reliably in an automated tour (each of the 84 skipped-RPC local updates
        // still triggers its own OWL reactive re-render of the whole grouped view, and Odoo's own
        // tour step schema caps any single step's own wait at a hard 60000ms - no way to raise it
        // further, and this operation's real wall-clock time varied wildly across repeated runs
        // during development, from ~4s to over a minute). The bulk-apply MECHANISM itself (a
        // dropdown resolving every row in a sub-group at once, Continue re-enabling once it does)
        // is already reliably covered by the separate 'ems_working_schedules_import_bulk_apply_
        // resolution' tour, at a realistic 2-3 row scale - this tour's own, non-duplicate job is
        // proving there is no CAP on how many rows load and get tracked at all, which the two
        // steps above already do conclusively.
        {
            trigger: ".modal .modal-footer button:contains('Cancel')",
            content: "Cancel - this tour only needs to prove every one of the 85 rows loaded and was correctly tracked, not resolve them all or complete the import",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal)) .o_list_view",
            content: "Back to the Working Schedules list, dialog closed cleanly",
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
            trigger: ".modal .alert-success:contains('Every subject matches its group')",
            content: "The 'subjects' screen shows the success message - no mismatch in this fixture",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'subjects' step (nothing to resolve here)",
            run: "click",
        },
        {
            trigger: ".modal .alert-success:contains('Every teacher mentioned in the file was recognized')",
            content: "The seeded teacher is recognized by e-mail",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'teachers' step (nothing to resolve here)",
            run: "click",
        },
        {
            trigger: ".modal .alert-success:contains('No conflicts were found within this batch')",
            content: "Only one teacher is in THIS batch, so no within-batch collision is possible",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue']",
            content: "Continue through the 'internal_conflicts' step (nothing to resolve here)",
            run: "click",
        },
        {
            trigger: ".modal .ems_conflict_row:contains('Tour Resolve DB Conflict Group A')",
            content: "The 'db_conflicts' screen lists the collision against the already-active DB session (Group A, the existing session, is the row under Group B's own file entry)",
        },
        {
            trigger: ".modal .modal-footer button[name='action_continue_disabled'][disabled]",
            content: "Continue shows disabled - both rooms still default to the same colliding classroom",
        },
        {
            trigger: ".modal .ems_conflict_row:contains('Tour Resolve DB Conflict Group A') .ems_conflict_space_right input",
            content: "Search for the seeded second classroom in the row's own right (existing DB session) room picker",
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

