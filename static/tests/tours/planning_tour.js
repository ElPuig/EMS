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
