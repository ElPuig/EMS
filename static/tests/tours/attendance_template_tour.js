/** @odoo-module **/

import { registry } from "@web/core/registry";

// ems.attendance_template (the weekly recurring class schedule setup - Community >
// Configuration > Teachers > ... ): only ever had a shallow color-widget smoke test
// (attendance_template_color_tour.js), never a real end-to-end save, including its own
// embedded "Sessions" tab (ems.attendance_schedule lines) and the widget="daterange"
// start_date/end_date fields. Without a saved template+schedule, the daily roll-call screen
// (attendance_passlist_tour.js) has nothing to show at all, so this is foundational, even
// though it's an admin/setup action rather than a daily one.
registry.category("web_tour.tours").add("ems_attendance_template_crud", {
    test: true,
    url: "/odoo/action-ems.action_attendance_template_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Attendance templates list loaded",
        },
        {
            trigger: ".o_list_button_add",
            content: "Create a new template",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='teacher_ids'] input",
            content: "Search for the seeded teacher",
            run: "edit Attendance Template Tour Teacher",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Attendance Template Tour Teacher')",
            content: "Select the teacher",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='level_id'] input",
            content: "Search for the seeded level",
            run: "edit Test Level (Attendance Template Tour)",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Test Level (Attendance Template Tour)')",
            content: "Select the level",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='study_id'] input",
            content: "Search for the seeded study",
            run: "edit Test Study (Attendance Template Tour)",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Test Study (Attendance Template Tour)')",
            content: "Select the study",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='group_ids'] input",
            content: "Search for the seeded group (domain-filtered by the study just picked)",
            run: "edit Attendance Template Tour Group",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Attendance Template Tour Group')",
            content: "Select the group",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='space_id'] input",
            content: "Search for the seeded space",
            run: "edit Test Space (Attendance Template Tour)",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Test Space (Attendance Template Tour)')",
            content: "Select the space",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='subject_id'] input",
            content: "Search for the seeded subject",
            run: "edit Test Subject (Attendance Template Tour)",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Test Subject (Attendance Template Tour)')",
            content: "Select the subject",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='start_date'] input[data-field='start_date']",
            content: "Fill in the start date (widget=\"daterange\")",
            run: "edit 01/01/2020",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='end_date'] input[data-field='end_date']",
            content: "Fill in the end date",
            run: "edit 12/31/2030",
        },
        {
            trigger: ".o_notebook .nav-link:contains('Students')",
            content: "Open the Students tab (student_ids, separate from Sessions, never rendered before)",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='student_ids']",
            content: "The (empty) students list renders without crashing",
        },
        {
            trigger: ".o_notebook .nav-link:contains('Sessions')",
            content: "Open the Sessions tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='attendance_schedule_ids'] .o_field_x2many_list_row_add a",
            content: "Add a schedule line",
            run: "click",
        },
        {
            trigger: ".o_selected_row .o_field_widget[name='weekday'] select",
            content: "Pick Monday",
            run: "selectByLabel Monday",
        },
        {
            trigger: ".o_selected_row .o_field_widget[name='space_id'] input",
            content: "Search for the seeded space on the schedule line",
            run: "edit Test Space (Attendance Template Tour)",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Test Space (Attendance Template Tour)')",
            content: "Select it",
            run: "click",
        },
        {
            trigger: ".o_selected_row .o_field_widget[name='start_time'] input",
            content: "Fill in the start time",
            run: "edit 08:00",
        },
        {
            trigger: ".o_selected_row .o_field_widget[name='end_time'] input",
            content: "Fill in the end time",
            run: "edit 09:00",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save the template",
            run: "click",
        },
        {
            trigger: ".o_form_button_save:not(:visible)",
            content: "Save completed",
        },
    ],
});
