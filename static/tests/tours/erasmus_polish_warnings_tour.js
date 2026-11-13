/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #787 - what is missing, said on the form. Records seeded by tests/test_erasmus_polish_warnings_tour.py.

// P11, P14, 8.8: the teacher's mobility says what to do now and lists their steps, ticked by them.
registry.category("web_tour.tours").add("ems_erasmus_warnings_teacher_steps", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .o_ems_erasmus_staff_next",
            content: "What to do now, on top of the mobility",
        },
        {
            trigger: ".o_form_view .o_notebook a[name='steps']",
            content: "Open the steps",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='task_ids'] .o_data_row button[name='action_staff_done']",
            content: "Tick a step as done",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='task_ids'] .o_data_row button[name='action_staff_undo']",
            content: "Ticked by the teacher, who can undo it",
        },
    ],
});

// 5.3, 8.1: the team's mobility says which step it is at and who has it.
registry.category("web_tour.tours").add("ems_erasmus_warnings_team_step", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .alert-info .o_field_widget[name='step_note']",
            content: "The step in progress, on top",
        },
    ],
});
