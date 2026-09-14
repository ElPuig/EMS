/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #444's follow-up (2026-09-12): a room change requested from a single teacher's own
// calendar (not a group-wide classroom change, issue #405) can also collide and be left
// pending. This tour proves the SAME banner + wizard UI (reused unchanged from the group-side
// flow) also renders and works from the teacher's own "Schedule" tab: the banner shows there,
// its button opens ems.group_classroom_change_wizard scoped by employee_id (no group_id), the
// reused conflict-lines widget renders the pending block as a "Room conflict" row, and resolving
// it ("Left prevails" - the requested room wins, the colliding session is archived) clears the
// banner. Seeded directly as already-pending via the ORM (the sync-time flagging itself is
// covered by tests/test_attendance_template.py's TestEmployeeSyncScheduleFromCalendar).
registry.category("web_tour.tours").add("ems_employee_classroom_change_wizard", {
    test: true,
    url: "/odoo/action-ems.action_employee_kanban",
    steps: () => [
        {
            trigger: ".o_control_panel",
            content: "Teachers loaded",
        },
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to list view",
            run: "click",
        },
        {
            // "0000 " prefix (same convention as tests/common.py's create_role_employee) sorts
            // the tour's own teacher first, so it's always on the list's first page without
            // needing a search step.
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('0000 Tour Teacher (Employee Classroom Change)')",
            content: "Open the tour's own teacher",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Schedule')",
            content: "Open the Schedule tab",
            run: "click",
        },
        {
            trigger: ".alert-warning:contains('1'):contains('teaching block')",
            content: "The pending-classroom banner shows on the teacher's own Schedule tab",
        },
        {
            trigger: ".alert-warning button[name='action_open_classroom_change_wizard']",
            content: "Open the resolution wizard",
            run: "click",
        },
        {
            trigger: ".modal .card-header:contains('Room conflict')",
            content: "The reused conflict-lines widget renders the pending block as a room conflict",
        },
        {
            trigger: ".modal .ems_conflict_row select",
            content: "Pick 'Left prevails' - the requested room wins, the colliding session is archived",
            run: "selectByLabel Left prevails",
        },
        {
            trigger: ".modal .modal-footer button[name='action_confirm']:not([disabled])",
            content: "Confirm",
            run: "click",
        },
        {
            trigger: ".o_form_view:not(:has(.modal)):not(:has(.alert-warning))",
            content: "Wizard closed and the pending-classroom banner is gone - nothing left to resolve",
        },
    ],
});
