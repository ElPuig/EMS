/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #478: a tutor opens their own student's Documentation tab, sees the Google credentials
// PDF (and nothing else), and gets a read-only document with no review buttons.
// Opened by URL on the seeded student (see test_student_document_tour.py).
registry.category("web_tour.tours").add("ems_student_document_tutor_credentials", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Documentation')",
            content: "Open the Documentation tab",
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
