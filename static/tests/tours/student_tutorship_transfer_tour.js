/** @odoo-module **/

import { registry } from "@web/core/registry";
import { searchStudent, studentCell } from "@ems/../tests/tours/student_list_helpers";

// Issue #807: the secretary's office transfers a student's tutorship to another group from the
// Studies tab; the student keeps their main group and its tutor shows as the official one.
registry.category("web_tour.tours").add("ems_student_tutorship_transfer", {
    test: true,
    url: "/odoo/action-ems.action_student_kanban",
    steps: () => [
        { trigger: ".o_switch_view.o_list", content: "Switch to list view", run: "click" },
        ...searchStudent("TTRT Transfer"),
        { trigger: `.o_list_view ${studentCell("0000 TTRT Transfer Student")}`, content: "Open the student", run: "click" },
        {
            trigger: ".o_form_view .o_notebook .nav-link[name='studies']",
            content: "Open the Studies tab",
            run: "click",
        },
        {
            trigger: ".o_form_view:has(.o_field_widget[name='tutor_id']):not(:has(.o_field_widget[name='official_tutor_id']))",
            content: "No transfer yet: no official tutor shown apart",
        },
        {
            trigger: ".o_field_widget[name='transferred_group_id'] input",
            content: "Transfer the tutorship to the 1st-year group",
            run: "edit TTRT1A",
        },
        {
            trigger: ".o-autocomplete--dropdown-menu li:contains('TTRT1A')",
            content: "Pick the group",
            run: "click",
        },
        { trigger: ".o_form_button_save", content: "Save", run: "click" },
        { trigger: ".o_form_view .o_form_saved", content: "Saved" },
        {
            trigger: ".o_field_widget[name='tutor_id']:contains('TTRT New Tutor')",
            content: "The tutor is now the 1st-year group's",
        },
        {
            trigger: ".o_field_widget[name='official_tutor_id']:contains('TTRT Official Tutor')",
            content: "The main group's tutor shows as the official one (Esfer@)",
        },
    ],
});

// The new tutor (a plain teacher, the least privileged role that tutors) finds the transferred
// student among their own students in every view of the action, and may edit them.
registry.category("web_tour.tours").add("ems_student_tutorship_transfer_new_tutor", {
    test: true,
    url: "/odoo/action-ems.action_student_kanban",
    steps: () => [
        {
            trigger: ".o_kanban_view .o_kanban_record:contains('TTRT Transfer Student'):contains('TTRT New Tutor')",
            content: "Kanban: the student shows with their new tutor",
        },
        { trigger: ".o_switch_view.o_list", content: "Switch to list view", run: "click" },
        ...searchStudent("TTRT Transfer"),
        { trigger: `.o_list_view ${studentCell("0000 TTRT Transfer Student")}`, content: "Open the student", run: "click" },
        {
            trigger: ".o_form_view .o_notebook .nav-link[name='studies']",
            content: "Open the Studies tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='transferred_group_id'].o_readonly_modifier:contains('TTRT1A')",
            content: "The tutor sees the transfer but can't change it",
        },
        {
            trigger: ".o_field_widget[name='mobile'] input",
            content: "The tutor may edit the student (a contact field)",
            run: "edit 600000807",
        },
        { trigger: ".o_form_button_save", content: "Save", run: "click" },
        { trigger: ".o_form_view .o_form_saved", content: "Saved" },
    ],
});
