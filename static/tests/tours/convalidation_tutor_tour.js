/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #864 - a tutor reads the convalidations of their tutees (and deletes their strikes).
// Records come from tests/test_convalidation_tutor_tour.py; selectors are structural, and the
// fixture tutor's language is English anyway.

// The student form's button opens the student's requests, and a request opens as the student sees
// it: its step, the subjects, and nothing decided (the request is waiting for the secretariat,
// with every subject granted).
registry.category("web_tour.tours").add("ems_convalidation_tutor_student", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .oe_stat_button[name='action_view_convalidations'] .o_stat_value:contains('1')",
            content: "The student's form counts their request",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='student_id']:contains('Convalidation Student')",
            content: "The request is listed",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='student_view_html']:contains('Test Subject One')",
            content: "The request shows its subject, as the student sees it",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='student_view_html']:contains('registering it')",
            content: "and the step it has reached",
        },
        {
            trigger: ".o_form_view:not(:has(.o_notebook .nav-link[name='subjects'])):not(:has(.o_field_widget[name='line_ids'])):not(:has(.o_field_widget[name='student_view_html'] th:contains('Resolution')))",
            content: "Nothing of what was decided is there",
        },
    ],
});

// A student with no request: the button is there, counting zero.
registry.category("web_tour.tours").add("ems_convalidation_tutor_zero", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .oe_stat_button[name='action_view_convalidations'] .o_stat_value:contains('0')",
            content: "The button is shown with a zero",
        },
    ],
});

// Academic management > Convalidations lists the requests of the tutor's tutees, in both views
// the list offers.
registry.category("web_tour.tours").add("ems_convalidation_tutor_menu", {
    test: true,
    url: "/odoo/action-ems.action_convalidation",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='student_id']:contains('Convalidation Student')",
            content: "Their tutee's open request is listed under the default filter",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='student_view_html']",
            content: "and opens as the student sees it",
        },
    ],
});

// The tutor deletes a strike a colleague issued to one of their tutees.
registry.category("web_tour.tours").add("ems_strike_tutor_delete", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .oe_stat_button[name='action_view_strikes']",
            content: "Open the student's strikes",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row .o_list_record_selector input",
            content: "Select the strike",
            run: "click",
        },
        {
            trigger: ".o_cp_action_menus button:has(.fa-cog)",
            content: "Open the list's action menu",
            run: "click",
        },
        {
            trigger: ".o-dropdown--menu .dropdown-item:contains('Delete')",
            content: "Delete it",
            run: "click",
        },
        {
            trigger: ".modal-footer .btn-primary",
            content: "Confirm",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_list_renderer:not(:has(.o_data_row))",
            content: "The strike is gone",
        },
    ],
});
