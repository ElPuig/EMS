/** @odoo-module **/

import { registry } from "@web/core/registry";
import { checkActions, clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

// A teacher opens a meeting held by email (issue #822): the form asks until when to answer instead
// of a time and a place, offers to open the thread rather than a call, and once open shows the
// interventions. Structural selectors, so the tour does not depend on the session language.
registry.category("web_tour.tours").add("ems_minute_thread_open", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .o_field_widget[name='reply_deadline']",
            content: "A thread asks until when the participants can answer",
        },
        {
            trigger: ".o_form_view:not(:has(.o_field_widget[name='attendance_mode'])):not(:has(.o_field_widget[name='duration']))",
            content: "It takes no attendance with the tag and lasts no hours",
        },
        {
            trigger: ".o_notebook .alert-info:visible",
            content: "The attendance tab says who gets the opening email",
        },
        ...checkActions({ offered: ["action_start_meeting", "action_delete"], notOffered: ["action_send_call", "action_submit"] },
            "A thread is opened, never called"),
        ...clickAction("action_start_meeting", "Open the thread"),
        {
            trigger: ".o_dialog .modal-footer .btn-primary",
            content: "Confirm opening it",
            run: "click",
        },
        {
            trigger: "div[name='block_interventions'] p.text-muted",
            content: "Nobody has answered yet",
        },
        {
            trigger: ".o_form_view:not(:has(div[name='block_amendments']:visible))",
            content: "There are no amendments while the thread is open",
        },
        ...checkActions({ offered: ["action_open_submit_dialog", "action_send_draft"], notOffered: ["action_back_to_draft", "action_send_call"] },
            "An open thread is sent for approval, and never goes back to being prepared"),
    ],
});

// Whoever writes the minute finds each answer as a card, which they can retouch.
registry.category("web_tour.tours").add("ems_minute_thread_interventions", {
    test: true,
    steps: () => [
        {
            trigger: "div[name='block_interventions'] .o_ems_record_card:contains('TMTT I agree with the item')",
            content: "The answer is filed as an intervention",
        },
        {
            trigger: "div[name='block_interventions'] .o_ems_record_card:not(:contains('the whole opening email'))",
            content: "Without the text it quotes",
        },
        {
            trigger: "div[name='block_attendance'] .o_field_widget[name='attendee_ids'] .o_tag:contains('TMTT Other')",
            content: "Whoever answered is among the attendees",
        },
    ],
});
