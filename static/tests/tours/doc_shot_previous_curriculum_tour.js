/** @odoo-module **/

import { registry } from "@web/core/registry";
import { clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";
import { uploadCertificate } from "@ems/../tests/tours/external_record_helpers";

// Doc screenshot (issue #672): the review grid of the previous curriculum import, read from an
// invented academic history the Python side serves through an xmlid.
registry.category("web_tour.tours").add("ems_doc_shot_previous_curriculum", {
    test: true,
    steps: () => [
        { trigger: ".o_form_view .o_form_sheet", content: "The student form is loaded" },
        ...clickAction("action_previous_curriculum_wizard", "Import a previous curriculum record"),
        uploadCertificate("ems.doc_shot_previous_curriculum_document"),
        {
            trigger: ".modal div[name='line_ids'] .o_data_row:contains('01401')",
            content: "The review grid is filled in, down to the work placement",
        },
    ],
});
