/** @odoo-module **/

import { registry } from "@web/core/registry";

// "Plannings" (action_planning_tree, ems.planning - the internal/external ponderation config
// per study+subject) had zero coverage. Selecting subject_id auto-populates
// planning_outcome_ids via an onchange (one row per outcome, split evenly, see
// EmsPlanning._onchange_planning_outcome_ids) - a subject with a single outcome (as seeded
// here) ends up with that one row already at 100%, so this tour only needs to confirm the
// tab renders it correctly, not add a line by hand.
registry.category("web_tour.tours").add("ems_planning_crud", {
    test: true,
    url: "/odoo/action-ems.action_planning_tree",
    steps: () => [
        { trigger: ".o_list_view", content: "Plannings list loaded" },
        { trigger: ".o_list_button_add", content: "Create a new planning", run: "click" },
        {
            trigger: ".o_form_view .o_field_widget[name='course_id'].o_readonly_modifier",
            content: "The course is shown read-only (defaulted to the current course)",
        },
        { trigger: ".o_form_view .o-mail-Chatter", content: "The chatter is rendered" },
        {
            trigger: ".o_form_view .o_field_widget[name='study_id'] input",
            content: "Search for the seeded study",
            run: "edit Test Study (Planning Tour)",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Test Study (Planning Tour)')",
            content: "Select the study",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='subject_id'] input",
            content: "Search for the seeded subject (domain now populated by study_id)",
            run: "edit Planning Tour Subject",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Planning Tour Subject')",
            content: "Select the subject",
            run: "click",
        },
        {
            trigger: ".o_notebook .nav-link:contains('Outcome ponderation')",
            content: "Open the Outcome ponderation tab",
            run: "click",
        },
        {
            trigger:
                ".o_field_widget[name='planning_outcome_ids'] .o_data_row:contains('Planning Tour Outcome')",
            content: "The subject's single outcome was auto-populated at 100% by the subject_id onchange",
        },
        { trigger: ".o_form_button_save", content: "Save", run: "click" },
        { trigger: ".o_form_button_save:not(:visible)", content: "Save completed" },
    ],
});

// Issue #503: Head of Studies/Deputy now see every planning (rule_planning_hos_all), so the
// list defaults to "Show only mine" (the subjects the logged-in user personally teaches) with
// an easy way to widen it back - same escape-hatch pattern as "My students"
// (contact_wpi_readonly_tour.js). Logged in as a Head of Studies (see test_planning_tour.py):
// a plain teacher's own read access is already limited to taught subjects, so removing the
// filter wouldn't reveal anything new for them.
registry.category("web_tour.tours").add("ems_planning_only_mine_filter", {
    test: true,
    url: "/odoo/action-ems.action_planning_tree",
    steps: () => [
        {
            trigger: ".o_searchview_facet:contains('Show only mine')",
            content: "The 'Show only mine' filter is active by default",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('Only Mine Taught Subject')",
            content: "The taught subject's planning is visible while the filter is active",
        },
        {
            trigger: ".o_searchview_facet:contains('Show only mine') .o_facet_remove",
            content: "Clear the default 'Show only mine' facet",
            run: "click",
        },
        {
            // Removing the facet reveals every planning centre-wide (this dev DB seeds well
            // over a page's worth), so a text search narrows back down to the fixture's own
            // row instead of relying on where it lands in the default alphabetical pagination.
            trigger: ".o_searchview_input",
            content: "Search for the other subject's planning by name",
            run: "edit Only Mine Other Subject && press Enter",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('Only Mine Other Subject')",
            content: "REGRESSION CHECK: the other subject's planning is reachable once the filter is removed",
        },
    ],
});

// Same escape-hatch pattern as "Show only mine" above, for the academic year: the list defaults
// to "Show only current course", removable to reach any past/future year's planning (a grade
// correction on an old course uses that year's own ponderations). The fixture subject has one
// planning in the current course and one in a past one (see test_planning_tour.py).
registry.category("web_tour.tours").add("ems_planning_only_current_course_filter", {
    test: true,
    url: "/odoo/action-ems.action_planning_tree",
    steps: () => [
        {
            trigger: ".o_searchview_facet:contains('Show only current course')",
            content: "The 'Show only current course' filter is active by default",
        },
        {
            trigger: ".o_searchview_input",
            content: "Narrow the list down to the fixture subject",
            run: "edit Current Course Filter Subject && press Enter",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('Current Course Filter Subject')",
            content: "The current course's planning is visible while the filter is active",
        },
        {
            trigger: ".o_list_view:not(:has(.o_data_row:contains('2001-2002')))",
            content: "The past course's planning is hidden while the filter is active",
        },
        {
            trigger: ".o_searchview_facet:contains('Show only current course') .o_facet_remove",
            content: "Clear the default 'Show only current course' facet",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('2001-2002')",
            content: "REGRESSION CHECK: the past course's planning is reachable once the filter is removed",
        },
    ],
});
