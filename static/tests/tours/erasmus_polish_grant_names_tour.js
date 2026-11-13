/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #790 - the grant and the subsidy in the order the money flows. Seeded by
// tests/test_erasmus_polish_grant_names.py (TestErasmusGrantNamesTour).
registry.category("web_tour.tours").add("ems_erasmus_polish_grant_names_group", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .o_notebook a[name='expenses']:contains('Grant and expenses')",
            content: "The money tab says what is inside (9.14)",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_group:has(.o_field_widget[name='grant_amount']):has(.o_field_widget[name='expense_amount']):has(.o_field_widget[name='pocket_total'])",
            content: "Grants, paid directly by the centre, to transfer (11.10)",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='pocket_paid_total']",
            content: "Transferred",
        },
        {
            trigger: ".o_form_view:not(:has(.o_field_widget[name='econ_committed']))",
            content: "Committed is the project's figure",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='grant_participant_ids'] th[data-name='pocket_paid']",
            content: "Each participant's transferred amount",
        },
    ],
});

registry.category("web_tour.tours").add("ems_erasmus_polish_grant_names_project", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .o_notebook a[name='economy']",
            content: "The Economy tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook .o_group:has(.o_field_widget[name='budget']):has(.o_field_widget[name='to_receive_amount'])",
            content: "The awarded subsidy with the rest of the subsidy (10.4)",
        },
        {
            trigger: ".o_form_view .o_form_sheet > .o_group:not(:has(.o_field_widget[name='budget']))",
            content: "Not on top any more",
        },
    ],
});
