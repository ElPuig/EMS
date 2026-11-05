/** @odoo-module **/

import { registry } from "@web/core/registry";
import { clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

// Issue #684 - Erasmus+ scoring and interviews. Every tour runs against records seeded by
// tests/test_erasmus_scoring_tour.py and uses structural selectors (field names, values), so the
// logged-in user's language does not matter.

const RUBRIC = ["motivation", "maturity", "difficulties", "adaptation", "comprehension", "fluency", "accuracy"];

// A plain teacher scores the interview assigned to them from Erasmus+ > My evaluations.
registry.category("web_tour.tours").add("ems_erasmus_my_evaluation", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_my_interviews",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='partner_id']:contains('Erasmus Test Student')",
            content: "The assigned interview is listed",
            run: "click",
        },
        ...RUBRIC.map((name) => ({
            trigger: `.o_form_view .o_field_widget[name='${name}'] input[data-value='4']`,
            content: `Score ${name}`,
            run: "click",
        })),
        {
            trigger: ".o_form_view .o_field_widget[name='english_score']:contains('12')",
            content: "The English part adds up",
        },
        ...clickAction("action_submit", "Submit the interview"),
        {
            trigger: ".o_form_view .o_statusbar_status button[data-value='submitted'].o_arrow_button_current",
            content: "The interview is submitted",
        },
    ],
});

// The Erasmus team records the manual criteria on the Scoring tab, then opens the interviews.
registry.category("web_tour.tours").add("ems_erasmus_scoring", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_application",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='partner_id']:contains('Erasmus Test Student')",
            content: "The admitted application is listed",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook a[name='scoring']",
            content: "Open the scoring tab",
            run: "click",
        },
        {
            // Selection values are JSON-encoded in the <select>, hence the quotes.
            trigger: ".o_form_view .o_field_widget[name='language_level'] select",
            content: "B2 certificate",
            run: 'select "b2"',
        },
        {
            trigger: ".o_form_view .o_field_widget[name='fewer_opportunities_check'] select",
            content: "Fewer opportunities not accredited",
            run: 'select "no"',
        },
        {
            trigger: ".o_form_view .o_field_widget[name='first_mobility'] select",
            content: "First mobility",
            run: 'select "yes"',
        },
        {
            trigger: ".o_form_view .o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_saved",
            content: "Saved",
        },
        {
            trigger: ".o_form_view .o_notebook a[name='interview']",
            content: "Open the interview tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='interview_ids'] .o_data_row td[name='evaluator_id']",
            content: "The assigned evaluator is listed",
        },
    ],
});

// The ranking of a closed call and the team's list of interviews open.
registry.category("web_tour.tours").add("ems_erasmus_ranking", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_ranking",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='partner_id']:contains('Erasmus Test Student')",
            content: "The admitted application is in the ranking",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='score_total']",
            content: "Its total is shown",
        },
    ],
});

// The Erasmus team's list of every interview, and one of them.
registry.category("web_tour.tours").add("ems_erasmus_ranking_interviews", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_interview",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='partner_id']:contains('Erasmus Test Student')",
            content: "The interview is listed",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='motivation']",
            content: "Its rubric is shown",
        },
    ],
});
