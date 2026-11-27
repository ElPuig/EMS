/** @odoo-module **/

import { registry } from "@web/core/registry";

// ems.grade_session_state_wizard: bulk state transition (open -> board/final) by level or
// study. Its sibling ems.grade_session_wizard already has a shallow smoke test
// (grade_session_tour.js), but neither wizard's widget="radio" mode field had ever actually
// been clicked/switched in a real browser - this tour does that (default 'study' mode ->
// 'level' mode, revealing level_ids and hiding study_ids) and drives the whole flow through
// to a real state change, verified against the DB afterward.
registry.category("web_tour.tours").add("ems_grade_session_state_wizard_apply", {
    test: true,
    url: "/odoo/action-ems.action_grade_session_state_wizard",
    steps: () => [
        {
            trigger: ".o_form_view .o_field_widget[name='mode'] input[type='radio']:checked",
            content: "Wizard loaded, 'By study' selected by default",
        },
        {
            // Selected by value, not by label: the labels are translated (this centre runs
            // in Catalan, where it reads "Per nivell"), so a :contains() on the English
            // string only passes until the .po files catch up.
            trigger: ".o_form_view .o_field_widget[name='mode'] input[type='radio'][data-value='level']",
            content: "Switch to 'By level' mode",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='level_ids']",
            content: "level_ids is now visible",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='level_ids'] input",
            content: "Pick the seeded level",
            run: "edit Test Level (Grade Session State Wizard Tour)",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Test Level (Grade Session State Wizard Tour)')",
            content: "Select it from the dropdown",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='level_ids'] .o_tag",
            content: "Level tag added",
        },
        {
            trigger: ".modal footer button[name='action_apply_state']",
            // This is a target="new" dialog (action_grade_session_state_wizard) - the
            // <footer> from the form's arch ends up a sibling of .o_form_view inside
            // .modal-content, not nested under it, unlike a directly-navigated action's own
            // page. A ".o_form_view footer ..." selector (which does work for a plain page)
            // silently never matches here - scope through ".modal" instead for any
            // dialog-rendered form's footer buttons.
            content: "Apply — round '1' defaults to target state 'Board'",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row",
            content: "Redirected to the affected grade sessions",
        },
    ],
});

// Issue #878: the same wizard on the sessions selected in the list (Actions > Change state). The
// last step also proves the screen is usable again: while the overlay is up, no trigger matches.
registry.category("web_tour.tours").add("ems_grade_session_state_from_list", {
    test: true,
    steps: () => [
        {
            // The action groups by round and group by default: drop the grouping to get plain rows.
            trigger: ".o_searchview_facet .o_facet_remove",
            content: "Remove the default grouping",
            run: "click",
        },
        {
            // Only this tour's group (the database may hold many other sessions).
            trigger: ".o_searchview_input",
            content: "Search the tour's group",
            run: "edit TGSSW",
        },
        { trigger: ".o_searchview_input", content: "Confirm the search", run: "press Enter" },
        {
            trigger: ".o_list_view .o_data_row:contains('TGSSW') .o_list_record_selector input",
            content: "Select the session",
            run: "click",
        },
        {
            trigger: ".o_control_panel .o_cp_action_menus button",
            content: "Open the Actions menu",
            run: "click",
        },
        {
            trigger: ".o-dropdown--menu .o-dropdown-item:contains('Change state')",
            content: "Change state",
            run: "click",
        },
        {
            trigger: ".modal .o_form_view .o_field_widget[name='target_state']",
            content: "Only the target state is asked: it acts on the selection",
        },
        {
            trigger: ".modal footer button[name='action_apply_state']",
            content: "Apply (board, the default)",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('TGSSW')",
            content: "Back on the list, usable again",
            run: "click",
        },
    ],
});
