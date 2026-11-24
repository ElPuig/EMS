/** @odoo-module **/

import { registry } from "@web/core/registry";
import { inputFiles } from "@web/../tests/utils";
import { clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

// Issue #835 - the VET coordinator completes the details of a certificate request their step
// requires (issue #851: one line per detail of the type) and hands it over to the next step. Runs against tests/test_certificate_tour.py's records, with
// structural selectors only (field and button names), so the user's language does not matter.
registry.category("web_tour.tours").add("ems_certificate_complete", {
    url: "/odoo/action-ems.action_certificate",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='student_name']:contains('TCTR Student')",
            content: "The request waiting for the coordinator is listed under Pending for me",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link[name='details']",
            content: "Open the certificate details",
            run: "click",
        },
        {
            // The details' names are the fixture's own text, not translatable labels.
            trigger: ".o_field_widget[name='value_ids'] .o_data_row:contains('Company') td[name='value_company_id']",
            content: "Edit the company detail",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='value_ids'] .o_selected_row .o_field_widget[name='value_company_id'] input",
            content: "Choose the collaborating company",
            run: "edit TCTR Company",
        },
        {
            trigger: ".o-autocomplete--dropdown-item a:contains('TCTR Company SL')",
            content: "Pick it from the suggestions",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='value_ids'] .o_data_row:contains('Hours') td[name='value_number']",
            content: "Edit the hours detail",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='value_ids'] .o_selected_row .o_field_widget[name='value_number'] input",
            content: "Write the hours",
            run: "edit 400",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link[name='documentation']",
            content: "Open the documentation",
            run: "click",
        },
        {
            // Its name is the fixture's own text, not a translatable label.
            trigger: ".o_field_widget[name='document_ids'] .o_data_row:contains('Training report') td[name='name']",
            content: "Open the required document only the coordinator's position attaches",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='attachment_ids'] .o_attach",
            content: "Attach its file",
            async run() {
                const files = [new File(["%PDF-1.4"], "Report.pdf", { type: "application/pdf" })];
                await inputFiles(".modal .o_field_widget[name='attachment_ids'] .o_input_file", files);
            },
        },
        {
            trigger: ".modal .o_field_widget[name='attachment_ids'] .o_attachment[title='Report.pdf']:not(.o_attachment_uploading)",
            content: "The file is uploaded",
        },
        {
            trigger: ".modal .o_form_button_save",
            content: "Keep it",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='document_ids'] .o_data_row:contains('Training report') td[name='attachment_ids']:contains('Report.pdf')",
            content: "The document shows its file",
        },
        ...clickAction("action_done_step", "Done: hand it over to the next step"),
        {
            trigger: ".o_form_view .o_field_widget[name='step_id']:contains('Issue')",
            content: "The request moves on to the step that issues it",
        },
        {
            trigger: ".o_form_view .o_form_saved",
            content: "And the form is saved",
        },
    ],
});

// The secretary already has every detail of a request still waiting for the coordinator: they
// issue it right away from the Actions dropdown, skipping the coordinator's step.
registry.category("web_tour.tours").add("ems_certificate_issue_now", {
    url: "/odoo/action-ems.action_certificate",
    steps: () => [
        {
            trigger: ".o_searchview .o_facet_remove",
            content: "The request is not pending for the secretary yet: drop the Pending for me filter",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='student_name']:contains('TCTR Ready Student')",
            content: "Open the request that is still with the coordinator",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='step_id']:contains('Complete')",
            content: "It is on the coordinator's step",
        },
        ...clickAction("action_issue_now", "Issue it now"),
        {
            trigger: ".modal .modal-footer .btn-primary",
            content: "Confirm every mandatory detail and document is there",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='step_id']:contains('Approve')",
            content: "The certificate is issued and waits for its approval",
        },
    ],
});

// Issue #858 - a former student is archived when they graduate or leave: the secretary still finds
// them in the Student dropdown when opening a request for them.
registry.category("web_tour.tours").add("ems_certificate_former_student", {
    url: "/odoo/action-ems.action_certificate/new",
    steps: () => [
        {
            trigger: ".o_form_view .o_field_widget[name='type_id'] input",
            content: "Choose the certificate type",
            run: "edit TCTR FCT",
        },
        {
            trigger: ".o-autocomplete--dropdown-item a:contains('TCTR FCT')",
            content: "Pick it",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='student_id'] input",
            content: "Look for the former student, who is archived",
            run: "edit TCTR Alumna",
        },
        {
            trigger: ".o-autocomplete--dropdown-item a:contains('TCTR Alumna Archived')",
            content: "They are offered",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='applicant_email'] input:value(tctr.alumna@example.com)",
            content: "Their details are filled in from the contact",
        },
        {
            trigger: ".o_form_view .o_form_button_save",
            content: "Save the request",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_saved",
            content: "And the form is saved",
        },
    ],
});
