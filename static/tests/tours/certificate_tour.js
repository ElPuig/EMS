/** @odoo-module **/

import { registry } from "@web/core/registry";
import { clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

// Issue #835 - the VET coordinator completes a certificate request's workplace training and hands
// it over to the next step. Runs against tests/test_certificate_tour.py's records, with
// structural selectors only (field and button names), so the user's language does not matter.
registry.category("web_tour.tours").add("ems_certificate_complete", {
    url: "/odoo/action-ems.action_certificate",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='student_id']:contains('TCTR Student')",
            content: "The request waiting for the coordinator is listed under Pending for me",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link[name='training']",
            content: "Open the workplace training",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='training_company_id'] input",
            content: "Choose the collaborating company",
            run: "edit TCTR Company",
        },
        {
            trigger: ".o-autocomplete--dropdown-item a:contains('TCTR Company SL')",
            content: "Pick it from the suggestions",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='hours'] input",
            content: "Write the hours",
            run: "edit 400",
        },
        ...clickAction("action_done_step", "Done: hand it over to the next step"),
        {
            trigger: ".o_form_view .o_field_widget[name='step_id']:contains('Issue')",
            content: "The request moves on to the step that issues it",
        },
        {
            trigger: ".o_form_view .o_form_saved",
            content: "And the form is saved",
        },
    ],
});
