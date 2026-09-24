/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #276 - subject convalidations. Every tour runs against records seeded by
// tests/test_convalidation_tour.py and uses structural selectors (button names, CSS classes),
// so the logged-in user's language does not matter.

// The Head of Studies resolves a request from Academic management > Convalidations: grants the
// subject, grades it and hands the request over to the secretariat.
registry.category("web_tour.tours").add("ems_convalidation_resolve", {
    test: true,
    url: "/odoo/action-ems.action_convalidation",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='student_id']:contains('Convalidation Student')",
            content: "The pending request is listed under the default filters",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_statusbar_status button[data-value='pending'].o_arrow_button_current",
            content: "The request opens as pending",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='line_ids'] .o_data_row button[name='action_grant']",
            content: "Convalidate the requested subject",
            run: "click",
        },
        {
            // The grade only shows on a granted line: waiting for the default 5 means the grant
            // has been saved and the row re-rendered, so the click below is not lost to it.
            trigger: ".o_form_view .o_field_widget[name='line_ids'] .o_data_row td[name='grade']:contains('5')",
            content: "Write the grade the previous studies hold",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='line_ids'] .o_data_row td[name='grade'] input",
            content: "Replace the default 5",
            run: "edit 8",
        },
        {
            trigger: ".o_form_view button[name='action_validate']",
            content: "Hand the request over to the secretariat",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_statusbar_status button[data-value='in_progress'].o_arrow_button_current",
            content: "The request is now the secretariat's",
        },
        {
            trigger: ".o_notebook .nav-link[name='documents']",
            content: "Open the supporting documents page",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='attachment_ids'] .o_attachment",
            content: "The uploaded certificate is listed",
        },
    ],
});

// The secretariat registers the resolution in Esfera and completes the request.
registry.category("web_tour.tours").add("ems_convalidation_complete", {
    test: true,
    url: "/odoo/action-ems.action_convalidation",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='student_id']:contains('Convalidation Student')",
            content: "The validated request is listed for the secretariat too",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_statusbar_status button[data-value='in_progress'].o_arrow_button_current",
            content: "It is waiting for the secretariat",
        },
        {
            trigger: ".o_form_view button[name='action_complete']",
            content: "Complete it",
            run: "click",
        },
        {
            trigger: ".modal footer button.btn-primary",
            content: "Confirm publishing the grades",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_statusbar_status button[data-value='completed'].o_arrow_button_current",
            content: "The request is completed",
        },
    ],
});

// The student form's stat button opens the student's requests.
registry.category("web_tour.tours").add("ems_convalidation_student_button", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .oe_stat_button[name='action_view_convalidations']",
            content: "Open the student's convalidations",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='student_id']:contains('Convalidation Student')",
            content: "The student's request is listed",
        },
    ],
});

// A convalidated subject reads CV in the teacher's grade matrix...
registry.category("web_tour.tours").add("ems_convalidation_grade_matrix", {
    test: true,
    steps: () => [
        {
            trigger: ".o_grade_matrix tbody tr td.o_grade_matrix_final:contains('CV')",
            content: "The convalidated student's final grade reads CV",
        },
    ],
});

// ...and in the tutor's per-student view.
registry.category("web_tour.tours").add("ems_convalidation_grade_tutor_matrix", {
    test: true,
    url: "/odoo/action-ems.action_grade_tutor_matrix",
    steps: () => [
        {
            trigger: ".o_grade_tutor tbody tr td.o_grade_matrix_final:contains('CV')",
            content: "The convalidated subject's final grade reads CV",
        },
    ],
});

// A portal student files a request.
registry.category("web_tour.tours").add("ems_portal_convalidation_submit", {
    test: true,
    url: "/my/convalidaciones",
    steps: () => [
        {
            // Tour triggers only match visible nodes, so the folded state is read off the toggle.
            trigger: ".o_ems_convalidation_new .o_ems_convalidation_toggle.collapsed",
            content: "The new-request form starts folded; unfold it",
            run: "click",
        },
        {
            trigger: ".o_ems_convalidation_new #convalidation_new_body.show input[name='subject_ids']:first",
            content: "Mark the first subject",
            run: "click",
        },
        {
            trigger: ".o_ems_convalidation_new select[name='basis']",
            content: "Pick the grounds",
            run: "selectByIndex 1",
        },
        {
            trigger: ".o_ems_convalidation_new input[name='documents']",
            content: "Attach a certificate",
            run() {
                const transfer = new DataTransfer();
                transfer.items.add(new File(["%PDF-1.4 tour"], "certificate.pdf", { type: "application/pdf" }));
                this.anchor.files = transfer.files;
            },
        },
        {
            trigger: ".o_ems_convalidation_new textarea[name='student_notes']",
            content: "Add a comment",
            run: "edit Passed in another cycle",
        },
        {
            trigger: ".o_ems_convalidation_new button[type='submit']",
            content: "Submit the request",
            run: "click",
            expectUnloadPage: true,
        },
        {
            trigger: ".o_ems_convalidation_submitted",
            content: "The confirmation is shown",
        },
        {
            trigger: ".o_ems_convalidation_request form[action^='/my/convalidaciones/cancel/']",
            content: "The new request is listed and can still be cancelled",
        },
        {
            trigger: ".o_ems_convalidation_reply textarea[name='message']",
            content: "Answer the request with more documentation",
            run: "edit Here is the certificate",
        },
        {
            trigger: ".o_ems_convalidation_reply input[name='documents']",
            content: "Attach it",
            run() {
                const transfer = new DataTransfer();
                transfer.items.add(new File(["%PDF-1.4 reply"], "reply.pdf", { type: "application/pdf" }));
                this.anchor.files = transfer.files;
            },
        },
        {
            trigger: ".o_ems_convalidation_reply button[type='submit']",
            content: "Send the answer",
            run: "click",
            expectUnloadPage: true,
        },
        {
            trigger: ".o_ems_convalidation_replied",
            content: "The answer is confirmed",
        },
    ],
});

// A teacher finds a subject convalidated during the running course in the academic history:
// the course's record is open already, marked as the current one.
// Opened straight from its URL: the history list starts grouped by course (the list itself is
// covered by year_record_tour.js).
registry.category("web_tour.tours").add("ems_convalidation_history_current_course", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .ribbon",
            content: "It is marked as the current course",
        },
        {
            trigger: ".o_form_view .alert-info",
            content: "and explains the rest of the subjects come when the course closes",
        },
        {
            trigger: ".o_form_view .o_data_row td[name='convalidation_number']:contains('CONV-')",
            content: "The convalidated subject carries its registration number",
        },
    ],
});
