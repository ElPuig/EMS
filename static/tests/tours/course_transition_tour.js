/** @odoo-module **/

import { registry } from "@web/core/registry";

/**
 * Preview only. The apply is deliberately never clicked: it deletes the operational
 * records of the outgoing course and cannot be undone, so it is covered by
 * TransactionCase tests instead (tests/test_course_transition.py), which roll back.
 */
registry.category("web_tour.tours").add("course_transition_preview_tour", {
    url: "/odoo/action-ems.action_course_transition_wizard",
    steps: () => [
        {
            content: "The wizard opens on its scope selection",
            trigger: ".modal .o_form_view div[name='study_ids']",
            run: () => {},
        },
        {
            content: "Run the dry run",
            trigger: ".modal footer button[name='action_preview']",
            run: "click",
        },
        {
            content: "The preview reports what the apply would do",
            trigger: ".modal div[name='delete_count']",
            run: () => {},
        },
        {
            content: "And it lists the students one by one",
            trigger: ".modal div[name='line_ids'] .o_list_view",
            run: () => {},
        },
        {
            content: "Leave without applying",
            trigger: ".modal footer button[special='cancel']",
            run: "click",
        },
    ],
});
