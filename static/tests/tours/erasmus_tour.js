/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #683 - Erasmus+ calls and applications. Every tour runs against records seeded by
// tests/test_erasmus_tour.py and uses structural selectors (field names, CSS classes), so the
// logged-in user's language does not matter.

// A student applies from the portal: opens the call, answers, uploads the required document and
// submits.
registry.category("web_tour.tours").add("ems_portal_erasmus_apply", {
    test: true,
    url: "/my/erasmus",
    steps: () => [
        {
            trigger: ".o_ems_erasmus_call a.o_ems_erasmus_apply",
            content: "The open call offers to apply",
            run: "click",
        },
        {
            trigger: "form.o_ems_erasmus_form textarea[name='availability']",
            content: "Say when you are available",
            run: "edit Summer",
        },
        {
            trigger: "form.o_ems_erasmus_form .o_ems_erasmus_document.o_ems_erasmus_required input[type='file']",
            content: "Attach the required document",
            run() {
                const transfer = new DataTransfer();
                transfer.items.add(new File(["%PDF-1.4 tour"], "cv.pdf", { type: "application/pdf" }));
                const input = document.querySelector(
                    "form.o_ems_erasmus_form .o_ems_erasmus_document.o_ems_erasmus_required input[type='file']");
                input.files = transfer.files;
                input.dispatchEvent(new Event("change", { bubbles: true }));
            },
        },
        {
            trigger: "form.o_ems_erasmus_form button[name='submit']",
            content: "Submit the application",
            run: "click",
        },
        {
            trigger: ".o_ems_erasmus_submitted",
            content: "The application is confirmed as submitted",
        },
        {
            trigger: ".o_ems_erasmus_application.o_ems_erasmus_state_submitted",
            content: "It is listed as submitted",
        },
    ],
});

// The Erasmus team reviews a submitted application from Erasmus+ > Applications: marks the
// document valid, records the requirements check and saves. Then opens the calls.
registry.category("web_tour.tours").add("ems_erasmus_review", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_application",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='partner_id']:contains('Erasmus Test Student')",
            content: "The submitted application is listed",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='document_ids'] .o_data_row button[name='action_mark_valid']",
            content: "Mark the uploaded document as valid",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='document_ids'] .o_data_row td[name='review_state']:not(:contains('Pending'))",
            content: "The document is no longer pending",
        },
        {
            // Selection values are JSON-encoded in the <select>, hence the quotes.
            trigger: ".o_form_view .o_field_widget[name='requirements_check'] select",
            content: "Record that the requirements are met",
            run: 'select "met"',
        },
        {
            trigger: ".o_form_view .o_field_widget[name='sanction_check'] span",
            content: "The sanction check is read-only for the Erasmus team",
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
        {
            trigger: ".o_form_view .o_field_widget[name='requirements_check_user_id']:contains('Test Erasmus User')",
            content: "The check records who made it",
        },
    ],
});

registry.category("web_tour.tours").add("ems_erasmus_calls", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_call",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='name']:contains('Test Erasmus Call')",
            content: "The call is listed",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='modality_ids'] .o_data_row",
            content: "Its modalities are shown",
        },
        {
            trigger: ".o_form_view .o_notebook a[name='documents']",
            content: "Open the documents tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='document_ids'] .o_data_row",
            content: "Its documents are shown",
        },
    ],
});

// The Head of Studies records the serious-sanction check, the one thing reserved to them.
registry.category("web_tour.tours").add("ems_erasmus_sanction_check", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_application",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='partner_id']:contains('Erasmus Test Student')",
            content: "The Head of Studies sees the application",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='sanction_check'] select",
            content: "Record that there is no serious sanction",
            run: 'select "met"',
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
