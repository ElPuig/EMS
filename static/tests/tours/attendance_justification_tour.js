/** @odoo-module **/

import { registry } from "@web/core/registry";

// ems.attendance_justification (Attendances > Justifications): had zero browser coverage.
// Creating a NEW justification through the UI needs widget="daterange" (a separate,
// non-trivial bespoke-widget investigation of its own) - this tour instead opens a
// pre-seeded justification, walks its three read-only notebook tabs (Affected sessions /
// Affected teachers / Attached files) to confirm none crash on render, and edits+saves the
// plain "Notes" tab to prove the form is genuinely interactive.
registry.category("web_tour.tours").add("ems_attendance_justification_open_and_edit", {
    test: true,
    url: "/odoo/action-ems.action_attendance_justification_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Justifications list loaded",
        },
        {
            trigger: ".o_list_view .o_data_row td:contains('Attendance Justification Tour Student')",
            content: "Open the seeded justification",
            run: "click",
        },
        {
            trigger: ".o_notebook .nav-link:contains('Affected sessions')",
            content: "Open Affected sessions tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='attendance_session_line_ids']",
            content: "The (empty) affected-sessions list renders without crashing",
        },
        {
            trigger: ".o_notebook .nav-link:contains('Affected teachers')",
            content: "Open Affected teachers tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='session_teacher_ids']",
            content: "The (empty) affected-teachers list renders without crashing",
        },
        {
            trigger: ".o_notebook .nav-link:contains('Attached files')",
            content: "Open Attached files tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='attachment_ids']",
            content: "The (empty) attachments list renders without crashing",
        },
        {
            trigger: ".o_notebook .nav-link:contains('Notes')",
            content: "Open Notes tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='notes'] textarea",
            content: "Edit the notes",
            run: "edit Tour note",
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
    ],
});

// Creating a brand-new justification through the UI: exercises widget="daterange" (confirmed
// working the same way as ems.attendance_template's own daterange fields, see
// attendance_template_tour.js - single combined-range widget here though, since the form only
// declares widget="daterange" on start_date with options={"end_date_field": "end_date"}, so
// BOTH date inputs render inside the start_date field's own widget container, not two separate
// field widgets), plus teacher_id -> student_id (domain filtered by allowed_student_ids,
// populated via the teacher_id onchange).
registry.category("web_tour.tours").add("ems_attendance_justification_create", {
    test: true,
    url: "/odoo/action-ems.action_attendance_justification_tree",
    steps: () => [
        { trigger: ".o_list_view", content: "Justifications list loaded" },
        { trigger: ".o_list_button_add", content: "Create a new justification", run: "click" },
        {
            trigger: ".o_form_view .o_field_widget[name='teacher_id'] input",
            content: "Search for the seeded teacher",
            run: "edit Attendance Justification Tour Teacher",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Attendance Justification Tour Teacher')",
            content: "Select the teacher",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='student_id'] input",
            content: "Search for the seeded student (domain now populated by the teacher_id onchange)",
            run: "edit Attendance Justification Tour Student 2",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Attendance Justification Tour Student 2')",
            content: "Select the student",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='start_date'] input[data-field='start_date']",
            content: "Fill in the start date (widget=\"daterange\", combined widget on start_date)",
            run: "edit 02/05/2026 09:00:00",
        },
        {
            trigger: ".o_field_widget[name='start_date'] input[data-field='end_date']",
            content: "Fill in the end date",
            run: "edit 02/05/2026 11:00:00",
        },
        { trigger: ".o_form_button_save", content: "Save", run: "click" },
        { trigger: ".o_form_button_save:not(:visible)", content: "Save completed" },
    ],
});
