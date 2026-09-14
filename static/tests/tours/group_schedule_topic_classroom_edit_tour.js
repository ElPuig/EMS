/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #446: ems.group_department_chief and above can edit a teaching block's topic/classroom
// directly from the group's own Schedule tab (ReadonlyScheduleGridField), without opening the
// teacher's own form. Proves both outcomes already covered at the model level by
// tests/test_group_schedule.py: a plain edit with no collision updates the block in place, and
// one that collides never blocks the save - it flags the block pending and the group's own
// pre-existing banner/wizard (issue #405/#444, unmodified) takes over from there.
//
// Card-based edit mode (developer feedback 2026-09-12: a per-block pencil icon was too fiddly to
// click) - mirrors the teacher's own editable grid: "Edit" switches every day's blocks into
// cards, only Topic/Classroom are editable on each, a single Save/Cancel applies to every card
// at once.
registry.category("web_tour.tours").add("ems_group_schedule_topic_classroom_edit", {
    test: true,
    url: "/odoo/action-ems.action_group_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Groups list loaded",
        },
        {
            trigger: ".o_searchview_input",
            content: "Search for the seeded group",
            run: "edit Tour Schedule Edit Group",
        },
        {
            trigger: ".o_searchview_input",
            content: "Confirm the search",
            run: "press Enter",
        },
        {
            trigger: ".o_list_view .o_data_row td:contains('Tour Schedule Edit Group')",
            content: "Open it",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Schedule')",
            content: "Open the Schedule tab",
            run: "click",
        },
        {
            trigger: ".o_schedule_grid_toolbar button:contains('Edit')",
            content: "Enter edit mode",
            run: "click",
        },
        {
            trigger: ".o_schedule_grid_card:has(.o_schedule_grid_card_readonly:contains('09:00-10:00')) .o_schedule_grid_card_topic",
            content: "Type a new topic",
            run: "edit Tour Topic Value",
        },
        {
            trigger: ".o_schedule_grid_card:has(.o_schedule_grid_card_readonly:contains('09:00-10:00')) .o_schedule_grid_card_space",
            content: "Pick the free classroom (no collision)",
            run: "selectByLabel TGSE-FREE",
        },
        {
            trigger: ".o_schedule_grid_toolbar button:contains('Save')",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_schedule_grid_entry_label:contains('Tour Topic Value')",
            content: "The block now shows the new topic",
        },
        {
            trigger: ".o_schedule_grid_entry_room:contains('Tour Free Space (Schedule Edit)')",
            content: "...and the new classroom",
        },
        {
            trigger: ".o_schedule_grid_toolbar button:contains('Edit')",
            content: "Edit again, this time into an already-occupied classroom",
            run: "click",
        },
        {
            trigger: ".o_schedule_grid_card:has(.o_schedule_grid_card_readonly:contains('09:00-10:00')) .o_schedule_grid_card_space",
            content: "Pick the colliding classroom",
            run: "selectByLabel TGSE-COLL",
        },
        {
            trigger: ".o_schedule_grid_toolbar button:contains('Save')",
            content: "Save - never blocked by the collision",
            run: "click",
        },
        {
            trigger: ".alert-warning:contains('1'):contains('teaching block')",
            content: "The pre-existing pending-classroom banner shows instead of a blocking error",
        },
        {
            trigger: ".o_schedule_grid_entry_room:contains('Tour Free Space (Schedule Edit)')",
            content: "The block itself stayed in its previous room - nothing moved without resolving the conflict",
        },
    ],
});
