/** @odoo-module **/

import { registry } from "@web/core/registry";

// Preparation tour for the academic-history manual screenshots (tests/
// test_docs_screenshots_academic_history.py). It only brings the screen to the state being
// photographed and stops there - the capture is what the test does afterwards, so it
// deliberately ends on a filled-in, unsaved form (see TestDocsScreenshots.allow_end_on_form).
registry.category("web_tour.tours").add("ems_doc_shot_grade_review", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view button.o_ems_grade_review",
            content: "Open the grade review wizard",
            run: "click",
        },
        { trigger: ".modal .o_form_view", content: "The wizard dialog opened" },
        {
            trigger: ".modal div[name='subject_record_id'] input",
            content: "Pick the subject the review corrects",
            run: "edit MP 0156",
        },
        {
            trigger: ".o-autocomplete--dropdown-item a:contains('MP 0156')",
            content: "Select it from the autocomplete",
            run: "click",
        },
        {
            trigger: ".modal .o_field_x2many_list .o_data_row:nth-child(3)",
            content: "The outcome grid was filled from the frozen record",
        },
        {
            trigger: ".modal .o_data_row:nth-child(2) [name='score']",
            content: "Open the resolved grade cell of the first failed outcome",
            run: "click",
        },
        {
            trigger: ".modal .o_data_row:nth-child(2) [name='score'] input",
            content: "Resolve it with a 5",
            run: "edit 5",
        },
        {
            trigger: ".modal .o_data_row:nth-child(3) [name='score']",
            content: "Open the resolved grade cell of the second failed outcome",
            run: "click",
        },
        {
            trigger: ".modal .o_data_row:nth-child(3) [name='score'] input",
            content: "Resolve it too",
            run: "edit 5",
        },
        {
            trigger: ".modal div[name='resolution'] textarea",
            content: "Write down what the review resolves",
            run: "edit Revisio de la qualificacio del modul: es resol com a superat amb un 5.",
        },
        {
            trigger: ".modal div[name='preview_state'] .badge",
            content: "The preview settled before the screenshot is taken",
        },
    ],
});
