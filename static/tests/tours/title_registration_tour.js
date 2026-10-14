/** @odoo-module **/

import { registry } from "@web/core/registry";
import { inputFiles } from "@web/../tests/utils";
import { clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

// Issue #635: titles obtained, registered in the academic history. Selectors are structural
// (field names, button names): the labels are translated.

// The secretariat imports a list of graduates (only the IDALU column) and registers the titles.
registry.category("web_tour.tours").add("ems_title_import", {
    test: true,
    steps: () => [
        {
            trigger: ".o_dialog .o_field_widget[name='course_id'] input",
            content: "The course comes preselected",
        },
        {
            trigger: ".o_dialog .o_field_widget[name='file']",
            content: "Attach the list of graduates",
            run: async () => {
                // The student created by tests/test_title_registration_tour.py.
                const file = new File(["IDALU\nTESTTITLETOUR1\n"], "graduats.csv", { type: "text/csv" });
                await inputFiles(".o_dialog .o_field_widget[name='file'] .o_input_file", [file]);
            },
        },
        {
            trigger: ".o_dialog .o_field_widget[name='file'] input.o_input:value(graduats.csv)",
            content: "File attached",
        },
        {
            trigger: ".o_dialog footer button[name='action_preview']",
            content: "Preview",
            run: "click",
        },
        {
            trigger: ".o_dialog .o_field_widget[name='line_ids'] .o_data_row.text-success",
            content: "The student with no group leaves as a graduate",
        },
        {
            trigger: ".o_dialog footer button[name='action_apply']",
            content: "Register the titles",
            run: "click",
        },
        {
            trigger: ".o_dialog:not(:has(.o_form_view)) .modal-footer .btn-primary",
            content: "Confirm",
            run: "click",
        },
        {
            trigger: ".o_dialog .o_field_widget[name='result_html'] p",
            content: "The result stays in the wizard, with the import log",
        },
        {
            trigger: ".o_dialog .o_field_widget[name='log_file']",
            content: "The import log can be downloaded again",
        },
    ],
});

// The secretariat registers a title from the student's own form.
registry.category("web_tour.tours").add("ems_title_register", {
    test: true,
    steps: () => [
        ...clickAction("action_title_register_wizard", "Register title from the Actions dropdown"),
        {
            trigger: ".o_dialog .o_field_widget[name='course_id'] input",
            content: "The latest course without a title comes preselected",
        },
        {
            trigger: ".o_dialog .alert-warning",
            content: "The student has no group: warned that they leave the centre",
        },
        {
            trigger: ".o_dialog footer button[name='action_apply']",
            content: "Register the title",
            run: "click",
        },
        {
            trigger: ".o_notification",
            content: "The result is notified",
        },
    ],
});
