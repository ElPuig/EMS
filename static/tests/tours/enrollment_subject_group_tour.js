/** @odoo-module **/

import { registry } from "@web/core/registry";

// Studies tab of a 2nd-year student: the subject dropdown only offers subjects of the
// student's own study, and a subject the 1st-year enrollment template sells goes to the
// 1st-year group instead of the student's main group (ems.enrollment._onchange_subject_id).
registry.category("web_tour.tours").add("ems_enrollment_subject_group", {
    test: true,
    url: "/odoo/action-ems.action_student_kanban",
    steps: () => [
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to list view",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('0000 TESGT Student')",
            content: "Open the student",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Studies')",
            content: "Open the Studies tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='enrollment_ids'] .o_field_x2many_list_row_add a",
            content: "Add a subject",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='enrollment_ids'] .o_data_row .o_field_widget[name='subject_id'] input",
            content: "Search the fixture subjects",
            run: "edit TESGT",
        },
        {
            trigger: ".o-autocomplete--dropdown-menu:has(li:contains('TESGT First Year Module')):not(:has(li:contains('TESGT Foreign Module')))",
            content: "Only the student's own study subjects are offered",
        },
        {
            trigger: ".o-autocomplete--dropdown-menu li:contains('TESGT First Year Module')",
            content: "Pick the 1st-year subject",
            run: "click",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_form_button_save:not(:visible)",
            content: "Save completed",
        },
        {
            trigger: ".o_field_widget[name='enrollment_ids'] .o_data_row .o_data_cell:contains('TESGT1A')",
            content: "The subject went to the 1st-year group, not the student's 2nd-year one",
        },
    ],
});
