/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #780 - the default texts of a call and a group mobility created by someone whose language
// is English, read by a Spanish-speaking Mobility technician. Records seeded by
// tests/test_erasmus_polish_default_data_tour.py.

registry.category("web_tour.tours").add("ems_erasmus_default_data_call", {
    test: true,
    steps: () => [
        {
            trigger: ".o_list_renderer .o_data_row td[name='name']:contains('Test default data tour call')",
            content: "Open the call from the list",
            run: "click",
        },
        {
            trigger: ".o_notebook a.nav-link[name='documents']",
            content: "Open the application documents",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='document_ids'] td:contains('CV Europass en inglés')",
            content: "The default document, in the reader's language",
        },
    ],
});

registry.category("web_tour.tours").add("ems_erasmus_default_data_group", {
    test: true,
    steps: () => [
        {
            trigger: ".o_kanban_record:contains('Test SMX2 morning')",
            content: "The group mobility, on its card",
        },
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to the list",
            run: "click",
        },
        {
            trigger: ".o_list_renderer .o_data_row td[name='name']:contains('Test SMX2 morning')",
            content: "Open the group mobility from the list",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='tie_break']:contains('Inscrito dentro del plazo')",
            content: "The default selection criteria, in the reader's language",
        },
    ],
});
