/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #880: the tutor opens the evaluation board minute EMS created when the group's sessions
// reached the board, finds its sections filled in and writes a comment for a family.
// Structural selectors only.
registry.category("web_tour.tours").add("ems_minute_board", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view div[name='block_board_difficulties'] .o_data_row:nth-child(4)",
            content: "The four difficulty areas are there",
        },
        {
            trigger: ".o_form_view div[name='block_board_statistics'] .o_field_widget[name='board_working_count']",
            content: "The statistics are there",
        },
        {
            trigger: ".o_form_view div[name='block_board_students'] .o_data_row td[name='family_comment']",
            content: "Edit the first student's comment for the family",
            run: "click",
        },
        {
            trigger: ".o_form_view div[name='block_board_students'] .o_data_row .o_field_widget[name='family_comment'] textarea",
            content: "Write it",
            run: "edit Keep working on RA2.",
        },
        {
            trigger: ".o_form_view .o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_saved",
            content: "Saved",
        },
    ],
});
