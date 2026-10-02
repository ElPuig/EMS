/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #534, Studies tab: switch on "Custom schedule", customize the subject (its group's
// sessions become editable slots), drop Tuesday with group C and add Wednesday with group D.
registry.category("web_tour.tours").add("ems_enrollment_slot", {
    test: true,
    url: "/odoo/action-ems.action_student_kanban",
    steps: () => [
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to list view",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('0000 TSLT Split Student')",
            content: "Open the student",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Studies')",
            content: "Open the Studies tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='custom_schedule'] input",
            content: "Switch on the custom schedule",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='enrollment_ids'] .o_data_row button[name='action_customize_slots']",
            content: "Customize the subject",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='enrollment_slot_ids'] .o_data_row:nth-child(2)",
            content: "Its group's two sessions are now slots",
        },
        {
            trigger: ".o_field_widget[name='enrollment_slot_ids'] .o_data_row:contains('Tuesday') .o_list_record_remove",
            content: "Drop Tuesday",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='enrollment_slot_ids'] .o_field_x2many_list_row_add a",
            content: "Add a slot",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='enrollment_slot_ids'] .o_selected_row .o_field_widget[name='enrollment_id'] input",
            content: "Pick the subject",
            run: "edit TSLT Split",
        },
        {
            trigger: ".o-autocomplete--dropdown-menu li:contains('TSLT Split Subject')",
            content: "Select it",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='enrollment_slot_ids'] .o_selected_row .o_field_widget[name='group_id'] input",
            content: "Pick group D",
            run: "edit TSLT1D",
        },
        {
            trigger: ".o-autocomplete--dropdown-menu li:contains('TSLT1D')",
            content: "Select it",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='enrollment_slot_ids'] .o_selected_row .o_field_widget[name='attendance_schedule_id'] input",
            content: "Pick the session",
            run: "edit Wednesday",
        },
        {
            trigger: ".o-autocomplete--dropdown-menu li:contains('Wednesday')",
            content: "Select Wednesday",
            run: "click",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_form_button_save:not(:visible)",
            content: "Save completed",
        },
        {
            trigger: ".o_field_widget[name='enrollment_slot_ids'] .o_data_row:contains('TSLT1D'):contains('Wednesday')",
            content: "The Wednesday slot with group D is saved",
        },
        {
            trigger: ".o_field_widget[name='enrollment_slot_ids']:not(:has(.o_data_row:contains('Tuesday')))",
            content: "Tuesday is gone",
        },
    ],
});
