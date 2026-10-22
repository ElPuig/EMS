/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #478: a tutor opens their own student's Documentation tab, sees the Google credentials
// PDF (and nothing else), and gets a read-only document with no review buttons.
// Opened by URL on the seeded student (see test_student_document_tour.py).
registry.category("web_tour.tours").add("ems_student_document_tutor_credentials", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .o_notebook .nav-link[name='secretary']",
            content: "Open the Secretary tab, home of the documentation section",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='document_ids'] .o_data_row:contains('Google Workspace credentials') a:contains('credentials.pdf')",
            content: "The credentials PDF is listed with its download link",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='document_ids']:not(:has(.o_data_row:contains('DNI')))",
            content: "The student's DNI stays hidden from the tutor",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='document_ids'] .o_data_row:contains('Google Workspace credentials') td[name='doc_type']",
            content: "Open the credentials document",
            run: "click",
        },
        {
            trigger: ".modal .o_form_view:not(:has(button[name='action_reset_to_pending'])):not(:has(button[name='action_approve']))",
            content: "The document opens without review buttons",
        },
    ],
});

// Issue #654: the Head of Studies opens Academic management > Student Documents and sees every
// document of the students below them (their DNI too), never another chain's, read only and
// without review buttons, in the list and in the form.
// Opened by URL on the action (see test_student_document_tour.py).
registry.category("web_tour.tours").add("ems_student_document_head_of_studies", {
    test: true,
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row:contains('0000 HoS Doc Tour Student')",
            content: "The pending DNI of a student below the Head of Studies is listed",
        },
        {
            trigger: ".o_list_view:not(:has(.o_data_row:contains('0000 HoS Doc Tour Other Student')))",
            content: "Another chain's student stays out",
        },
        {
            trigger: ".o_list_view:not(:has(button[name='action_approve'])):not(:has(.o_list_button_add))",
            content: "No review buttons and no New button: read only",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('0000 HoS Doc Tour Student') td[name='partner_id']",
            content: "Open the document",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='partner_id']:contains('0000 HoS Doc Tour Student')",
            content: "The document's form opens",
        },
        {
            trigger: ".o_form_view:not(:has(button[name='action_approve'])):not(:has(button[name='action_reset_to_pending']))",
            content: "The form has no review buttons",
        },
    ],
});
