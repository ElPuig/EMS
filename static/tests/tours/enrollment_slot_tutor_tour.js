/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #534, as the student's tutor: the enrollment list is read-only (no "Add a line" - only the
// secretary's office and academic administration add or remove enrollments), but its row buttons
// still customize the subject's sessions.
registry.category("web_tour.tours").add("ems_enrollment_slot_tutor", {
    test: true,
    url: "/odoo/action-ems.action_student_kanban",
    steps: () => [
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to list view",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('0000 TSLT Split Student')",
            content: "Open the student",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Studies')",
            content: "Open the Studies tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='enrollment_ids']:not(:has(.o_field_x2many_list_row_add))",
            content: "The tutor can't add enrollments",
        },
        {
            trigger: ".o_field_widget[name='custom_schedule'] input:not([disabled])",
            content: "Switch on the custom schedule",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='enrollment_ids'] .o_data_row button[name='action_customize_slots']",
            content: "Customize the subject",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='enrollment_slot_ids'] .o_data_row:nth-child(2)",
            content: "Its group's two sessions are now slots",
        },
        {
            trigger: ".o_field_widget[name='enrollment_ids'] .o_data_row button[name='action_set_remote']",
            content: "Mark it as not in person",
            run: "click",
        },
        {
            trigger: ".modal-footer .btn-primary",
            content: "Confirm",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='enrollment_ids'] .o_data_row.text-muted button[name='action_follow_group']",
            content: "The subject is now not in person (muted row, 'follow the group' offered)",
        },
    ],
});
