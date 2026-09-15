/** @odoo-module **/

import { registry } from "@web/core/registry";

// Not a regression test: tests/test_docs_screenshots.py runs these to put a screen into the state
// a manual shows, then photographs it. Driving it through a real tour rather than setting input
// values from a script matters - Odoo's own `edit` action types the way a person does, and a
// value merely assigned from JavaScript was lost again right after the group was picked.
//
// No `url`: the capture opens the screen itself and starts the tour where it already is. The
// authorization comes preloaded, so no autocomplete dropdown other than the group's is ever
// opened - one left open covers the form and lists whatever the database holds.
registry.category("web_tour.tours").add("ems_doc_shot_tutor_send", {
    test: true,
    steps: () => [
        {
            trigger: ".o_dialog div[name='group_ids'] input",
            content: "Type the tutor's own group",
            run: "edit DAM1A",
        },
        {
            trigger: ".o-autocomplete--dropdown-item a:contains(DAM1A)",
            run: "click",
        },
        {
            trigger: ".o_dialog div[name='line_ids'] .o_data_row td:contains(Marina Exemple)",
            content: "The preview lists the group's students",
        },
    ],
});
