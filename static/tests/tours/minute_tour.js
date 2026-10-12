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
            trigger: ".o_notebook .nav-link:contains('Content'), .o_notebook .nav-item:nth-child(5) .nav-link",
            content: "The sections tab is there",
            run: "click",
        },
        {
            // If the type declared sections, the minute must already have rows here: an empty
            // table means the layout never got built, which is the point of this step.
            trigger: ".o_field_x2many .o_data_row",
            content: "The sections of this type are already laid out",
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
            trigger: "button[name='action_open_attendance_kiosk']",
            content: "The kiosk of the meeting is ready to be opened",
        },
        ...checkActions({ offered: ["action_send_call", "action_submit"], notOffered: ["action_approve"] },
            "A draft offers to send the call and to send the minute for approval"),
        ...clickAction("action_submit", "Send it for approval"),
        {
            trigger: ".o_statusbar_status .o_arrow_button_current",
            content: "The state moved on",
        },
    ],
});
