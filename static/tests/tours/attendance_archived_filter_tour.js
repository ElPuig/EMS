/** @odoo-module **/

import { registry } from "@web/core/registry";

// Phase 8 of plans/course_transition_teacher_schedule_archival.md: "an explicit 'show archived'
// affordance for ems.attendance_template/resource.calendar/ems.attendance_session_header" -
// neither of the first two search views declared a "Archived" filter at all (resource.calendar
// already has one natively, inherited unchanged), so an archived record was simply unreachable
// from the list view's own search bar. These tours only prove the filter now exists and works -
// the archiving mechanics themselves are covered elsewhere (test_course_transition.py and friends).
registry.category("web_tour.tours").add("ems_attendance_template_archived_filter", {
    test: true,
    url: "/odoo/action-ems.action_attendance_template_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Templates list loaded",
        },
        // Narrows to just the seeded record first (this is a shared dev DB that can already have
        // other archived templates from unrelated fixtures/pagination) - the Archived filter's
        // own effect is then checked against this single, unambiguous result.
        {
            trigger: ".o_searchview_input",
            content: "Search for the seeded subject",
            run: "edit Tour Archived Template",
        },
        {
            // Two fields are declared on this search view (teacher_ids, subject_id) - pressing
            // Enter blindly would pick whichever candidate is focused by default, not necessarily
            // 'Subject', so the specific dropdown item is targeted explicitly instead.
            trigger: ".o_searchview_autocomplete .o_menu_item:contains('Subject')",
            content: "Pick the 'Subject' search candidate specifically",
            run: "click",
        },
        {
            trigger: ".o_list_view:not(:has(.o_data_row))",
            content: "The archived template is hidden by default",
        },
        {
            trigger: ".o_searchview_dropdown_toggler",
            content: "Open the search dropdown",
            run: "click",
        },
        {
            trigger: ".o_filter_menu .o_menu_item:contains('Archived')",
            content: "Enable the 'Archived' filter",
            run: "click",
        },
        {
            trigger: ".o_data_row",
            content: "DEBUG: any row at all after search+filter",
        },
    ],
});

registry.category("web_tour.tours").add("ems_attendance_session_archived_filter", {
    test: true,
    url: "/odoo/action-ems.action_attendance_session_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Session history list loaded",
        },
        {
            trigger: ".o_searchview_input",
            content: "Search for the seeded teacher",
            run: "edit Tour Archived Session Teacher",
        },
        {
            trigger: ".o_searchview_autocomplete .o_menu_item:contains('Teacher')",
            content: "Pick the 'Teacher' search candidate specifically",
            run: "click",
        },
        {
            trigger: ".o_list_view:not(:has(.o_data_row))",
            content: "The archived session is hidden by default",
        },
        {
            trigger: ".o_searchview_dropdown_toggler",
            content: "Open the search dropdown",
            run: "click",
        },
        {
            trigger: ".o_filter_menu .o_menu_item:contains('Archived')",
            content: "Enable the 'Archived' filter",
            run: "click",
        },
        {
            trigger: ".o_data_row:contains('Tour Archived Session Teacher')",
            content: "The archived session now shows",
        },
    ],
});

registry.category("web_tour.tours").add("ems_working_schedule_course_grouping", {
    test: true,
    url: "/odoo/action-ems.action_working_schedules_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Working schedules list loaded",
        },
        {
            trigger: ".o_searchview_dropdown_toggler",
            content: "Open the search dropdown",
            run: "click",
        },
        {
            trigger: ".o_group_by_menu .o_menu_item:contains('Course')",
            content: "Group by the new 'Course' option",
            run: "click",
        },
        {
            trigger: ".o_group_header:contains('2199-2200')",
            content: "A group header for the seeded course appears",
        },
    ],
});
