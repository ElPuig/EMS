/** @odoo-module **/

import { registry } from "@web/core/registry";

// "Work placement evaluation (EM)" (action_em_grading_wizard) had zero coverage, including
// its bespoke widget="em_matrix" (a plain-<input> grid, simpler than the dblclick-to-edit
// grade_matrix/grade_tutor_matrix widgets - a plain "edit" tour action works directly).
registry.category("web_tour.tours").add("ems_em_grading_wizard_apply", {
    test: true,
    url: "/odoo/action-ems.action_em_grading_wizard",
    steps: () => [
        {
            trigger: ".o_form_view .o_field_widget[name='study_id'] input",
            content: "Search for the seeded study",
            run: "edit Test Study (EM Grading Wizard Tour)",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Test Study (EM Grading Wizard Tour)')",
            content: "Select the study",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='group_id'] input",
            content: "Search for the seeded group (domain now populated by study_id)",
            run: "edit EGWT1A",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('EGWT1A')",
            content: "Select the group",
            run: "click",
        },
        {
            // The matrix's first cell shows only student_firstname (lastname is a separate cell).
            trigger: ".o_em_matrix tbody tr td:contains('EmgwtStudent')",
            content: "The matrix rendered with the seeded student's row",
        },
        {
            trigger: ".o_em_matrix tbody tr input[data-column='0']",
            content: "Fill in the student's overall EM score",
            run: "edit 7",
        },
        {
            trigger: ".o_form_statusbar button[name='action_apply']",
            content: "Apply changes",
            run: "click",
        },
        // action_apply() re-fetches and re-renders the whole matrix (_fill_lines()) from the
        // DB - wait for that reload to fully settle (the score still reads "7") before ending
        // the tour, or the harness can catch the form mid-reload and flag it as "finished in
        // edition mode" (confirmed happening only under full-suite load, not in isolation).
        {
            trigger: ".o_em_matrix tbody tr input[data-column='0']:value(7)",
            content: "The applied score is confirmed after the reload",
        },
    ],
});
