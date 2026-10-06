/** @odoo-module **/

import { registry } from "@web/core/registry";
import { clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";
import { uploadCertificate } from "@ems/../tests/tours/external_record_helpers";

// Preparation tour for the "Add a previous record" manual screenshot (tests/
// test_docs_screenshots_academic_history.py): opens the wizard from the student form, uploads the
// invented academic record PDF and stops on the filled-in review grid, which is what the test
// then photographs (it deliberately ends on an unsaved form, see allow_end_on_form).
registry.category("web_tour.tours").add("ems_doc_shot_previous_record", {
    test: true,
    steps: () => [
        { trigger: ".o_form_view .o_form_sheet", content: "The student form is loaded" },
        ...clickAction("action_external_record_wizard", "Add a previous record"),
        uploadCertificate("ems.doc_shot_previous_record_certificate"),
        {
            trigger: ".modal div[name='line_ids'] .o_data_row:contains('M_OP_01 + M_OP_02')",
            content: "The review grid is filled in, down to the recognised optional module",
        },
    ],
});
