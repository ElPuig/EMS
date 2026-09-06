/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #395: a tutor can now change their tutorand's main group (e.g. moving the student
// from group A to group B) - this field used to be locked by 'is_tutor_readonly' for tutors
// (see views/community/contact/form.xml). Changing it also moves the student's subject
// enrollments that were in the old group over to the new one (res.partner.write() /
// ems.enrollment._ems_move_group), verified here in the embedded enrollment list after save.
registry.category("web_tour.tours").add("ems_contact_group_change", {
    test: true,
    url: "/odoo/action-ems.action_student_kanban",
    steps: () => [
        {
            trigger: ".o_control_panel",
            content: "Educational Community loaded (already scoped to this tutor's own tutorands)",
        },
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to list view",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('0000 Group Change Tour Student')",
            content: "Open the tutorand",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Studies')",
            content: "Open the Studies tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='main_group_id'] input",
            content: "REGRESSION CHECK: the tutor can edit the student's main group",
            run: "edit TCGC1B",
        },
        {
            trigger: ".o-autocomplete--dropdown-menu li:contains('TCGC1B')",
            content: "Select the new group",
            run: "click",
        },
        {
            trigger: ".alert-warning:contains('Saving will move')",
            content: "The pending-change warning appears before saving (res.partner.main_group_pending_change)",
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
            trigger: ".o_field_widget[name='enrollment_ids'] .o_data_row .o_data_cell:contains('TCGC1B')",
            content: "The subject enrollment followed the student from the old group to the new one",
        },
    ],
});
