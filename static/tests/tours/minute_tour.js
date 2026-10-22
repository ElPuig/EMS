/** @odoo-module **/

import { registry } from "@web/core/registry";
import { checkActions, clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

// A department head writes a department minute end to end: the type lays out the sections, the
// attendees arrive preloaded from the department, an agreement is added, and it goes for approval.
// Structural selectors rather than label text, so the tour does not depend on the session language.
registry.category("web_tour.tours").add("ems_minute_write", {
    test: true,
    url: "/odoo/action-ems.action_minute",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Minutes list opens with its default facets",
        },
        {
            trigger: ".o_list_button_add",
            content: "Start a new minute",
            run: "click",
        },
        {
            // Before anything is chosen the form asks for the type and nothing else.
            trigger: ".o_form_view:not(:has(.o_notebook)) .o_field_widget[name='code_preview']:contains('ACTA')",
            content: "A new minute starts with its type, with no tabs yet",
        },
        {
            // The type names are the centre's own data, the same in every language.
            trigger: ".o_form_view .o_field_widget[name='type_id'] input",
            content: "Look for the department minute",
            run: "edit departament",
        },
        {
            trigger: ".o-autocomplete--dropdown-menu li:contains('departament')",
            content: "Pick the type, which is what lays the minute out",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='department_id'] input",
            content: "The type asks for its department right after",
            run: "edit 0000 Minute Tour",
        },
        {
            trigger: ".o-autocomplete--dropdown-menu li:contains('0000 Minute Tour Department')",
            content: "Pick the department",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='code_preview']:contains('ACTA-000DEP-'):contains('-001')",
            content: "The code has built up from the type, the department and the date",
        },
        {
            trigger: ".o_field_widget[name='start_datetime'] input",
            content: "The date and time come proposed",
        },
        {
            trigger: ".o_field_widget[name='duration'] input",
            content: "And so does how long the meeting lasts",
        },
        {
            trigger: ".o_field_widget[name='attendance_mode'] input[data-value='nfc']",
            content: "Attendance will be taken with the NFC tag",
            run: "click",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_form_saved .o_field_widget[name='code_preview']:contains('ACTA-000DEP-'):contains('-001')",
            content: "The code has been issued",
        },
        {
            trigger: ".o_notebook .nav-item:first-child .nav-link",
            content: "Back to the attendance tab",
            run: "click",
        },
        {
            // While the meeting is prepared the kiosk is not offered: it opens once the meeting starts.
            trigger: ".o_notebook .alert-info:not(:has(button[name='action_open_attendance_kiosk']))",
            content: "The kiosk waits for the meeting to start",
        },
        ...checkActions({ offered: ["action_send_call", "action_start_meeting", "action_delete"], notOffered: ["action_submit", "action_approve"] },
            "While it is prepared, a meeting offers to send its call, to start and to be deleted"),
        ...clickAction("action_start_meeting", "Start the meeting"),
        {
            trigger: ".o_dialog .modal-footer .btn-primary",
            content: "Confirm the change of state",
            run: "click",
        },
        {
            trigger: "div[name='block_attendance'] button[name='action_open_attendance_kiosk']",
            content: "Once the meeting has started, its kiosk is ready to be opened",
        },
        {
            // The type lays the minute out: its text sections are there, each with its own box
            // (the section names are the centre's own data, the same in every language).
            trigger: ".o_ems_text_block_title:contains('Precs i preguntes')",
            content: "The sections of this type are laid out",
        },
        {
            // The minute is now written from top to bottom: no tabs, one block after another.
            trigger: ".o_form_view:not(:has(.o_notebook)) .o_ems_text_block_add",
            content: "Add an item to discuss",
            run: "click",
        },
        {
            trigger: ".o_ems_text_block .o_ems_text_block_title .o_field_widget[name='name'] input",
            content: "Name the item",
            run: "edit Budget for the workshop",
        },
        {
            trigger: ".o_ems_text_block:has(.o_field_widget[name='name']) .o_ems_text_block_body .odoo-editor-editable",
            content: "Write what is said about it, in its own box",
            run: "editor The department agrees on the list of materials.",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_form_saved .o_ems_text_block .o_ems_text_block_body:contains('The department agrees on the list of materials.')",
            content: "What was written on the item is kept",
        },
        {
            trigger: ".o_ems_text_block_body .o-we-toolbar",
            content: "Each box has its formatting toolbar in sight",
        },
        {
            // A saved item is as editable as a new one: every box stays open for writing.
            trigger: ".o_ems_text_block:has(.o_field_widget[name='name']) .o_ems_text_block_body .odoo-editor-editable",
            content: "Go on writing on the item already saved",
            run: "editor Two quotes will be asked for.",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save again",
            run: "click",
        },
        {
            trigger: ".o_form_saved .o_ems_text_block .o_ems_text_block_body:contains('Two quotes will be asked for.')",
            content: "The change to the saved item is kept too",
        },
        {
            trigger: ".o_ems_text_block:has(.o_ems_text_block_title:contains('Precs i preguntes')) .odoo-editor-editable",
            content: "Write something and leave it there, without saving",
            run: "editor Nobody asks anything.",
        },
        {
            // Nobody clicked Save: the form did, in the writer's pause.
            trigger: ".o_form_saved .o_ems_text_block:contains('Nobody asks anything.')",
            content: "The minute saved itself",
            timeout: 40000,
        },
        {
            trigger: ".o_field_widget[name='agreement_ids'] .o_ems_record_card_add",
            content: "Add an agreement, which is a card of its own",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='agreement_ids'] .o_ems_record_card_body[data-name='name'] textarea",
            content: "Write what is agreed, at full width",
            run: "edit Buy the materials for the workshop",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save the agreement",
            run: "click",
        },
        {
            trigger: ".o_form_saved .o_field_widget[name='agreement_ids'] .o_ems_record_card_cell[data-name='code']:contains('ACORD-000DEP-')",
            content: "The agreement got its code",
        },
        ...clickAction("action_submit", "Send it for approval"),
        {
            trigger: ".o_dialog .modal-footer .btn-primary",
            content: "Confirm the change of state",
            run: "click",
        },
        {
            trigger: ".o_statusbar_status .o_arrow_button_current",
            content: "The state moved on",
        },
        ...checkActions({ offered: ["action_back_to_meeting"], notOffered: ["action_send_call", "action_delete"] },
            "Sent for approval, it can no longer be called nor deleted"),
    ],
});

// A teacher who only attended the meeting opens its minute: the form is plain reading - nothing to
// type into, no line to add, no action that would change it - instead of fields the save refuses.
registry.category("web_tour.tours").add("ems_minute_read_only", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .o_form_renderer.o_form_readonly .o_field_widget[name='attendee_ids']",
            content: "The minute opens read-only",
        },
        {
            trigger: ".o_form_view:not(:has(.o_form_editable)):not(:has([contenteditable='true'])):not(:has(.o_field_x2many_list_row_add))",
            content: "Nothing can be typed in or added",
        },
        {
            trigger: ".o_form_view:not(:has(.o_form_status_indicator_buttons:not(.invisible)))",
            content: "No save button",
        },
        {
            // Neither the Actions dropdown nor a lone header button (see actions_dropdown_helpers).
            trigger: ".o_form_view .o_form_statusbar:not(:has(.o_ems_actions_toggle)):not(:has(button[name^='action_']))",
            content: "No action that would change the minute",
        },
    ],
});
