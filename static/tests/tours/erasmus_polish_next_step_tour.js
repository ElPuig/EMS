/** @odoo-module **/

import { registry } from "@web/core/registry";
import { checkActions, mainAction } from "@ems/../tests/tours/actions_dropdown_helpers";

// Issue #786 - the next step of the teacher's application stays in view (o_ems_action_main), the rest
// in Actions. Records seeded by tests/test_erasmus_polish_next_step_tour.py.

// P04: nothing answered yet, filling in the form is the one action, in view.
registry.category("web_tour.tours").add("ems_erasmus_actions_teacher_fill", {
    test: true,
    steps: () => [
        mainAction("action_staff_edit", "Fill in the form, in view"),
        {
            trigger: ".o_form_view .o_form_statusbar:not(:has(.o_ems_actions_toggle))",
            content: "Nothing else to do: no Actions dropdown",
        },
    ],
});

// P10, P11: once answered, submitting is the next step in view; filling in again is in Actions.
registry.category("web_tour.tours").add("ems_erasmus_actions_teacher_submit", {
    test: true,
    steps: () => [
        mainAction("action_staff_submit", "Submit, in view"),
        ...checkActions({ offered: ["action_staff_edit"] }, "Filling in the form again, in Actions"),
    ],
});
