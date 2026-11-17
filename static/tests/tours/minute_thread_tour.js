/** @odoo-module **/

import { registry } from "@web/core/registry";
import { checkActions, clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

// A teacher opens a meeting held by email (issue #822): with that modality the form asks until
// when to answer instead of a time and a place, and offers to open the thread rather than a call.
// Structural selectors, so the tour does not depend on the session language.
registry.category("web_tour.tours").add("ems_minute_thread_open", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .o_field_widget[name='reply_deadline']",
            content: "A meeting held by email asks until when the participants can answer",
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
            "A meeting held by email is opened, never called"),
        ...clickAction("action_start_meeting", "Open the thread"),
        {
            trigger: ".o_dialog .modal-footer .btn-primary",
            content: "Confirm opening it",
            run: "click",
        },
        {
            trigger: "div[name='block_attendance'] .alert-info:visible",
            content: "The meeting says where the answers are written",
        },
        ...checkActions({ offered: ["action_open_submit_dialog", "action_send_draft", "action_open_intervention_wizard"],
            notOffered: ["action_back_to_draft", "action_send_call"] },
            "An open thread is sent for approval, and never goes back to being prepared"),
    ],
});

// A participant who only reads the minute finds the answers under any other business and adds an
// intervention on an item, which is written under that item.
registry.category("web_tour.tours").add("ems_minute_thread_interventions", {
    test: true,
    steps: () => [
        {
            trigger: "div[name='block_texts']:contains('TMTT I agree with the item')",
            content: "The answer by email is written under any other business",
        },
        {
            trigger: "div[name='block_texts']:not(:contains('the whole opening email'))",
            content: "Without the text it quotes",
        },
        {
            trigger: "div[name='block_attendance'] .o_field_widget[name='attendee_ids'] .o_tag:contains('TMTT Other')",
            content: "Whoever answered is among the attendees",
        },
        ...clickAction("action_open_intervention_wizard", "Add an intervention"),
        {
            trigger: ".o_dialog .o_field_widget[name='agenda_id'] input",
            content: "Choose the item it is about",
            run: "edit TMTT item",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('TMTT item')",
            run: "click",
        },
        {
            trigger: ".o_dialog .o_field_widget[name='body'] .odoo-editor-editable",
            content: "Write the intervention",
            run: "editor TMTT said on the item",
        },
        {
            trigger: ".o_dialog .modal-footer .btn-primary",
            content: "Add it",
            run: "click",
        },
        {
            trigger: "div[name='block_items']:contains('TMTT said on the item')",
            content: "It is written under the item",
        },
    ],
});
