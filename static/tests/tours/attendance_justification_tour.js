/** @odoo-module **/

import { registry } from "@web/core/registry";

// The list has real justifications too (the dev database's): find the fixture by its student
// instead of hoping it is on the first page.
function searchStudent(name) {
    return [
        { trigger: ".o_searchview_input", content: `Search for ${name}`, run: `edit ${name}` },
        { trigger: ".o_searchview_input", content: "Search by student (the first field)", run: "press Enter" },
        { trigger: ".o_searchview_facet", content: "Filtered by student" },
    ];
}

// ems.attendance_justification (Attendances > Justifications): had zero browser coverage.
// Creating a NEW justification through the UI needs widget="daterange" (a separate,
// non-trivial bespoke-widget investigation of its own) - this tour instead opens a
// pre-seeded justification, walks its three read-only notebook tabs (Affected sessions /
// Affected teachers / Attached files) to confirm none crash on render, and edits+saves the
// details of its reason ('Other') to prove the form is genuinely interactive.
registry.category("web_tour.tours").add("ems_attendance_justification_open_and_edit", {
    test: true,
    url: "/odoo/action-ems.action_attendance_justification_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Justifications list loaded",
        },
        ...searchStudent("Attendance Justification Tour Student"),
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
            trigger: ".o_field_widget[name='details'] textarea",
            content: "Edit the details of the reason 'Other' (issue #795)",
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

// Issue #469: a tutor opening a justification whose affected sessions were taught by other
// teachers - sessions the teacher record rules do not let the tutor read. Any AccessError
// raised while the form loads its data is logged to the console, which fails the tour.
registry.category("web_tour.tours").add("ems_attendance_justification_tutor_open", {
    test: true,
    url: "/odoo/action-ems.action_attendance_justification_tree",
    steps: () => [
        { trigger: ".o_list_view", content: "Justifications list loaded" },
        ...searchStudent("Attendance Justification Tutor Tour Student"),
        {
            trigger: ".o_list_view .o_data_row td:contains('Attendance Justification Tutor Tour Student')",
            content: "Open the justification",
            run: "click",
        },
        {
            trigger: ".o_notebook .nav-link:contains('Affected sessions')",
            content: "Open Affected sessions tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='attendance_session_line_ids'] .o_data_row:contains('Attendance Justification Tour Space')",
            content: "The other teacher's session is listed by name",
        },
    ],
});

// Issue #553: Head of Studies opening a justification whose file a tutor uploaded - the
// attachment used to stay unlinked (no res_id), so only its uploader could read it.
registry.category("web_tour.tours").add("ems_attendance_justification_hos_attachment", {
    test: true,
    url: "/odoo/action-ems.action_attendance_justification_tree",
    steps: () => [
        { trigger: ".o_list_view", content: "Justifications list loaded" },
        ...searchStudent("Attendance Justification Tutor Tour Student"),
        {
            trigger: ".o_list_view .o_data_row td:contains('Attendance Justification Tutor Tour Student')",
            content: "Open the justification",
            run: "click",
        },
        {
            trigger: ".o_notebook .nav-link:contains('Attached files')",
            content: "Open Attached files tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='attachment_ids'] .o_ems_attachment:contains('Tour justificant.txt'):not(:has(.o_ems_attachment_delete))",
            content: "The tutor's file is listed",
        },
        {
            trigger: ".o_field_widget[name='attachment_ids'] .o_ems_attachment:contains('Tour justificant.txt') .o_ems_attachment_preview",
            content: "Preview the file",
            run: "click",
        },
        {
            trigger: ".o-FileViewer .o-FileViewer-view",
            content: "Odoo's file viewer shows the file",
        },
    ],
});

// The tutor's own files (ems_attachments widget): uploading straight from the tab, named after
// the file, and removing one, which deletes it on save (ems.attachment_mixin).
registry.category("web_tour.tours").add("ems_attendance_justification_tutor_attachments", {
    test: true,
    url: "/odoo/action-ems.action_attendance_justification_tree",
    steps: () => [
        { trigger: ".o_list_view", content: "Justifications list loaded" },
        ...searchStudent("Attendance Justification Tutor Tour Student"),
        {
            trigger: ".o_list_view .o_data_row td:contains('Attendance Justification Tutor Tour Student')",
            content: "Open the justification",
            run: "click",
        },
        {
            trigger: ".o_notebook .nav-link:contains('Attached files')",
            content: "Open Attached files tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='attachment_ids'] .o_attach",
            content: "Upload a file straight from the tab",
            run() {
                const input = document.querySelector(".o_field_widget[name='attachment_ids'] input[type='file']");
                const transfer = new DataTransfer();
                transfer.items.add(new File(["uploaded"], "Tour upload.txt", { type: "text/plain" }));
                input.files = transfer.files;
                input.dispatchEvent(new Event("change", { bubbles: true }));
            },
        },
        {
            trigger: ".o_field_widget[name='attachment_ids'] .o_ems_attachment:contains('Tour upload.txt')",
            content: "The uploaded file is listed under its own name",
        },
        {
            trigger: ".o_field_widget[name='attachment_ids'] .o_ems_attachment:contains('Tour justificant.txt') .o_ems_attachment_delete",
            content: "Delete the earlier file",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='attachment_ids']:not(:has(.o_ems_attachment:contains('Tour justificant.txt')))",
            content: "The earlier file is gone",
        },
        { trigger: ".o_form_button_save", content: "Save", run: "click" },
        { trigger: ".o_form_button_save:not(:visible)", content: "Save completed" },
    ],
});

// Issue #795: "New" opens the justification form; a tutor adds a whole group of theirs at once
// ("Add groups"), takes out the groupmate who must not be justified, and saves a single
// justification shared by the rest.
registry.category("web_tour.tours").add("ems_attendance_justification_create", {
    test: true,
    url: "/odoo/action-ems.action_attendance_justification_tree",
    steps: () => [
        { trigger: ".o_list_view", content: "Justifications list loaded" },
        { trigger: ".o_list_button_add", content: "New justification", run: "click" },
        {
            trigger: ".o_form_view .o_field_widget[name='start_date'] input[data-field='start_date']",
            content: "Fill in the start date (widget=\"daterange\", combined widget on start_date)",
            run: "edit 02/05/2026 09:00:00",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='start_date'] input[data-field='end_date']",
            content: "Fill in the end date",
            run: "edit 02/05/2026 11:00:00",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='mode'] input[data-value='group']",
            content: "Justify a group",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='add_group_ids'] input",
            content: "Search for the tutor's group",
            run: "edit TJT1A",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('TJT1A')",
            content: "Pick the group",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='student_ids'] .o_data_row:contains('Attendance Justification Tutor Tour Student')",
            content: "The group's students are listed, with their group",
        },
        {
            trigger: ".o_field_widget[name='add_group_ids'] .o_tag:contains('TJT1A') .o_delete",
            content: "Issue #808: taking the group out of the picker",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='student_ids']:not(:has(.o_data_row))",
            content: "Its students leave the list",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='add_group_ids'] input",
            content: "Pick the group again",
            run: "edit TJT1A",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('TJT1A')",
            content: "Pick the group",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='student_ids'] .o_data_row:contains('Attendance Justification Tutor Tour Student')",
            content: "Its students are listed again",
        },
        {
            trigger: ".o_field_widget[name='student_ids'] .o_data_row:contains('Tour Excluded Student') .o_list_record_remove",
            content: "Take out the groupmate who must not be justified",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='student_ids']:not(:has(.o_data_row:contains('Tour Excluded Student')))",
            content: "The groupmate is no longer listed",
        },
        { trigger: ".o_form_button_save", content: "Save", run: "click" },
        { trigger: ".o_form_view .o_form_saved", content: "Saved" },
    ],
});

// Issue #808: a tutor justifies one single student, picking them directly (the default mode,
// no group at all).
registry.category("web_tour.tours").add("ems_attendance_justification_single_student", {
    test: true,
    url: "/odoo/action-ems.action_attendance_justification_tree",
    steps: () => [
        { trigger: ".o_list_view", content: "Justifications list loaded" },
        { trigger: ".o_list_button_add", content: "New justification", run: "click" },
        {
            trigger: ".o_form_view .o_field_widget[name='start_date'] input[data-field='start_date']",
            content: "Fill in the start date",
            run: "edit 02/09/2026 09:00:00",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='start_date'] input[data-field='end_date']",
            content: "Fill in the end date",
            run: "edit 02/09/2026 11:00:00",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='student_id'] input",
            content: "Search for the student (the default mode)",
            run: "edit Tour Excluded Student",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Tour Excluded Student')",
            content: "Pick the student",
            run: "click",
        },
        {
            trigger: ".o_form_view:not(:has(.o_field_widget[name='add_group_ids']))",
            content: "No group picker in student mode",
        },
        { trigger: ".o_form_button_save", content: "Save", run: "click" },
        { trigger: ".o_form_view .o_form_saved", content: "Saved" },
    ],
});

// Issue #795: a strike covers whole days. Choosing the reason "Strike" replaces the period with a
// single day, and the justification covers the student's whole day.
registry.category("web_tour.tours").add("ems_attendance_justification_strike", {
    test: true,
    url: "/odoo/action-ems.action_attendance_justification_tree",
    steps: () => [
        { trigger: ".o_list_view", content: "Justifications list loaded" },
        { trigger: ".o_list_button_add", content: "New justification", run: "click" },
        {
            trigger: ".o_form_view .o_field_widget[name='reason_id'] input",
            content: "Search for the reason",
            run: "edit Labour strike",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Labour strike')",
            content: "Pick Labour strike",
            run: "click",
        },
        {
            trigger: ".o_form_view:not(:has(.o_field_widget[name='start_date'] input[data-field='start_date'])) .o_field_widget[name='day'] input",
            content: "The period gives way to a single day",
            run: "edit 02/06/2026",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='mode'] input[data-value='group']",
            content: "Justify a group",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='add_group_ids'] input",
            content: "Search for the tutor's group",
            run: "edit TJT1A",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('TJT1A')",
            content: "Pick the group",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='student_ids'] .o_data_row:contains('Attendance Justification Tutor Tour Student')",
            content: "The group's students are listed",
        },
        { trigger: ".o_form_button_save", content: "Save", run: "click" },
        { trigger: ".o_form_view .o_form_saved", content: "Saved" },
    ],
});
