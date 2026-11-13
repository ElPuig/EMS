/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #791 - the Secretary enters a service paid by the centre for a group mobility (11.11), with
// one question saying who it is for (11.2). Seeded by tests/test_erasmus_polish_economy_services.py.
registry.category("web_tour.tours").add("ems_erasmus_polish_economy_services", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .alert-warning:contains('project expense')",
            content: "Nobody covered yet: it may be a project expense (11.1)",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='name'] input",
            content: "Invoice number",
            run: "edit F-TOUR-791",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='amount'] input",
            content: "Amount",
            run: "edit 900",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='project_id'] input",
            content: "Project",
            run: "edit TEST-GROUP-VET",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('TEST-GROUP-VET')",
            content: "Pick the project",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='covers'] input[data-value='group']",
            content: "For a group mobility",
            run: "click",
        },
        {
            trigger: ".o_form_view:not(:has(.o_field_widget[name='mobility_ids'])):not(:has(.o_field_widget[name='provision_ids']))",
            content: "Only the field that applies",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='group_mobility_id'] input",
            content: "The group mobility",
            run: "edit SMX2",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Test SMX2 morning')",
            content: "Pick it",
            run: "click",
        },
        {
            trigger: ".o_form_view:not(:has(.alert-warning:contains('project expense')))",
            content: "Someone is covered: no warning",
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
            trigger: ".o_form_view .o-mail-Chatter",
            content: "Its history (11.7)",
        },
    ],
});
