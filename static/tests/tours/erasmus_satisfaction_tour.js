/** @odoo-module **/

import { registry } from "@web/core/registry";

// Erasmus+ satisfaction survey on the portal (tests/test_erasmus_satisfaction.py): the participant
// opens it from the Erasmus+ page, gives a 4, confirms it and says what did not work. Structural
// selectors only, so the language does not matter.
registry.category("web_tour.tours").add("ems_erasmus_satisfaction_tour", {
    test: true,
    url: "/my/erasmus",
    steps: () => [
        {
            trigger: ".o_ems_erasmus_satisfaction_pending .o_ems_erasmus_satisfaction_open",
            content: "Open the pending survey",
            run: "click",
        },
        {
            trigger: ".o_ems_erasmus_satisfaction_scores label.o_ems_erasmus_score_4",
            content: "Give a 4",
            run: "click",
        },
        {
            trigger: ".o_ems_erasmus_satisfaction textarea[name='comment']",
            content: "Optional comment",
            run: "edit The company was nice",
        },
        {
            trigger: ".o_ems_erasmus_satisfaction_send",
            content: "Send",
            run: "click",
        },
        {
            trigger: ".o_ems_erasmus_satisfaction_confirm",
            content: "A low score asks whether it is right",
        },
        {
            trigger: ".o_ems_erasmus_satisfaction textarea[name='what_failed']",
            content: "What did not work",
            run: "edit The flights were late",
        },
        {
            trigger: ".o_ems_erasmus_satisfaction_send",
            content: "Send",
            run: "click",
        },
        {
            trigger: ".o_ems_erasmus_satisfaction_thanks",
            content: "Thanks, and the survey is no longer pending",
        },
        {
            trigger: "body:not(:has(.o_ems_erasmus_satisfaction_pending))",
            content: "Nothing pending",
        },
    ],
});
