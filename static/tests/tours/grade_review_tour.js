/** @odoo-module **/

import { registry } from "@web/core/registry";

// The grade review wizard (issue #493): the only write path into an academic file already closed.
// Driven as the secretariat, the least-privileged role that must reach the screen - the whole
// point of the issue is that this is secretariat work, and every other field of the history
// stays read-only for everyone.
//
// Covers the three renderings the feature adds: the button on the year record form, the wizard
// dialog itself (its outcome grid and its live preview), and the corrected values landing back
// on the record's own Subjects list.
registry.category("web_tour.tours").add("ems_grade_review", {
    test: true,
    url: "/odoo/action-ems.action_year_record_list",
    steps: () => [
        { trigger: ".o_list_view", content: "Academic history list loaded" },
        {
            trigger: ".o_searchview_input",
            content: "Search for the seeded student",
            run: "edit Grade Review Tour Student",
        },
        { trigger: ".o_searchview_input", content: "Confirm the search", run: "press Enter" },
        {
            trigger: ".o_searchview_facet:contains('Grade Review Tour Student')",
            content: "The search facet is applied",
        },
        // The action's own context defaults to grouping by course.
        {
            trigger: ".o_searchview_facet:contains('Course') .o_facet_remove",
            content: "Remove the default 'Course' grouping facet",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_cell:contains('Grade Review Tour Student')",
            content: "Open the seeded year record",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_data_cell:contains('Grade Review Tour Subject')",
            content: "The Subjects tab rendered with the failed subject",
        },
        {
            trigger: ".o_form_view button.o_ems_grade_review",
            content: "Open the grade review wizard",
            run: "click",
        },
        { trigger: ".modal .o_form_view", content: "The wizard dialog opened" },
        {
            trigger: ".modal div[name='subject_record_id'] input",
            content: "Pick the subject the review corrects",
            run: "edit Grade Review Tour Subject",
        },
        {
            trigger: ".o-autocomplete--dropdown-item a:contains('Grade Review Tour Subject')",
            content: "Select it from the autocomplete",
            run: "click",
        },
        {
            trigger: ".modal .o_field_x2many_list .o_data_row:nth-child(2)",
            content: "The outcome grid was filled from the frozen record",
        },
        {
            trigger: ".modal .o_data_row:nth-child(2) [name='score']",
            content: "Open the resolved grade cell of the failed outcome",
            run: "click",
        },
        {
            trigger: ".modal .o_data_row:nth-child(2) [name='score'] input",
            content: "Resolve it with a 5",
            run: "edit 5",
        },
        {
            trigger: ".modal div[name='resolution'] textarea",
            content: "Write down what the review resolves",
            run: "edit Reviewed after the closure: the module is passed.",
        },
        {
            // The preview is computed from the very same helper that writes the record, so a
            // wrong preview here is a wrong write.
            trigger: ".modal div[name='preview_state'] .badge:contains('Passed')",
            content: "The preview already shows the subject as passed",
        },
        {
            trigger: ".modal div[name='proposed_result']:contains('Fully passed')",
            content: "...and proposes the course result the correction yields",
        },
        {
            trigger: ".modal footer button[name='action_apply']",
            content: "Apply the review",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_data_row:first-child td[name='state']:contains('Passed')",
            content: "The subject is passed on the record's own Subjects list",
        },
        {
            // hoot-dom's :value() reads the select's own value, so this asserts on the stored
            // key rather than on a translatable label.
            trigger: ".o_form_view .o_field_widget[name='academic_result'] select:value(full)",
            content: "...and the course result was updated with it",
        },
    ],
});
