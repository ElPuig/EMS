/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #402: a teacher issues a strike outside any attendance session (e.g. a student
// caught in the corridor), from the "New strike" button of Coexistence > Strikes, then
// checks it is listed. Driven by a plain teacher (see tests/test_strike_issue_standalone_tour.py).
registry.category("web_tour.tours").add("ems_strike_issue_standalone", {
    test: true,
    url: "/odoo/action-ems.action_strike_list",
    steps: () => [
        {
            trigger: ".o_list_view .o_list_button_add_strike",
            content: "Open the New strike dialog",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='teacher_id'].o_readonly_modifier:contains('Test Teacher User')",
            content: "The issuer is the logged-in teacher, read-only",
        },
        {
            trigger: ".modal .o_form_view .o_field_widget[name='student_id'] input",
            content: "Search for the student",
            run: "edit Strike Standalone Student",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Strike Standalone Student')",
            content: "Select the student",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='reason_id'] input",
            content: "The reason is required, so the dialog must preselect the default one",
            run: function () {
                if (!this.anchor.value) {
                    throw new Error("The default strike reason is not preselected");
                }
            },
        },
        {
            trigger: ".modal .o_field_widget[name='kicked_out'] input",
            content: "Mark it as kicked out",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='notes'] textarea",
            content: "Add the details",
            run: "edit Caught running in the corridor",
        },
        {
            trigger: ".modal footer button.o_strike_issue_send",
            content: "Send",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal))",
            content: "The dialog closes",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='notes']:contains('Caught running in the corridor')",
            content: "The new strike is listed without reloading the page",
        },
    ],
});
