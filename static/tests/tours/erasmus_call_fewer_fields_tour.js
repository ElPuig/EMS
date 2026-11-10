/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #767 - fewer fields when opening a call, as the Mobility technician. Records seeded by
// tests/test_erasmus_call_fewer_fields_tour.py.

function openCall(name) {
    return [
        {
            trigger: `.o_list_view .o_data_row td[name='name']:contains('${name}')`,
            content: "Open the call from the list",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_inner_group:has(.o_field_widget[name='audience']):has(.o_field_widget[name='rules_document']):not(:has(.o_field_widget[name='date_close']))",
            content: "Settings block (note 2.3)",
        },
        {
            trigger: ".o_form_view .o_inner_group:has(.o_field_widget[name='date_close']):has(details.o_ems_erasmus_call_deadlines):not(:has(.o_field_widget[name='audience']))",
            content: "Calendar block (note 2.3)",
        },
        {
            trigger: ".o_form_view:not(:has(.o_field_widget[name='is_accepting'])):not(:has(.o_field_widget[name='reminder_days']))",
            content: "Neither the grey 'Accepting applications' (note 2.6) nor the reminder",
        },
    ];
}

function unfoldDeadlines() {
    return [
        {
            trigger: ".o_form_view details.o_ems_erasmus_call_deadlines:not([open])",
            content: "The deadlines start folded",
        },
        {
            trigger: ".o_form_view details.o_ems_erasmus_call_deadlines > summary",
            content: "Unfold them",
            run: "click",
        },
        {
            trigger: ".o_form_view details.o_ems_erasmus_call_deadlines[open] .o_field_widget[name='claims_deadline'] input",
            content: "The claims deadline is there, filled in",
        },
    ];
}

registry.category("web_tour.tours").add("ems_erasmus_call_fewer_fields_student", {
    test: true,
    steps: () => [
        ...openCall("Test Erasmus Call"),
        ...unfoldDeadlines(),
        {
            trigger: ".o_form_view .alert-warning:contains('Claims deadline')",
            content: "The claims deadline before the closing date is warned (note 2.4)",
        },
        {
            trigger: ".o_field_widget[name='modality_ids'] table:not(:has(th[data-name='project'])):not(:has(th[data-name='period'])):not(:has(th[data-name='destinations']))",
            content: "Modalities: no project, period nor destinations",
        },
        {
            trigger: ".o_form_view .o_notebook:not(:has(a.nav-link[name='mobility_block']))",
            content: "No Mobility block before the definitive resolution",
        },
        {
            trigger: ".o_form_view .o_notebook a.nav-link[name='documents']",
            content: "The application documents stay",
        },
    ],
});

registry.category("web_tour.tours").add("ems_erasmus_call_fewer_fields_mobility", {
    test: true,
    steps: () => [
        ...openCall("Test Erasmus Call"),
        {
            trigger: ".o_form_view .o_notebook a.nav-link[name='mobility_block']",
            content: "The Mobility block, once the definitive resolution is published",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook a.nav-link[name='preparation_documents']",
            content: "With its mobility documents",
        },
    ],
});

registry.category("web_tour.tours").add("ems_erasmus_call_fewer_fields_staff", {
    test: true,
    steps: () => [
        ...openCall("Test Erasmus Staff Call"),
        ...unfoldDeadlines(),
        {
            trigger: ".o_form_view label:contains('rating deadline')",
            content: "In a staff call it is the commission's deadline",
        },
        {
            trigger: ".o_field_widget[name='modality_ids'] table th[data-name='project']",
            content: "A staff modality keeps its project",
        },
        {
            trigger: ".o_form_view .o_notebook:not(:has(a.nav-link[name='documents'])):not(:has(a.nav-link[name='panel'])):not(:has(a.nav-link[name='mobility_block']))",
            content: "No Documents, Panel nor Mobility while the call is open",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='staff_level_ids']",
            content: "Teachers of stays",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='validator_ids']",
            content: "Validates the activities stays",
        },
    ],
});
