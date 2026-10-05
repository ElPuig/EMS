/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #393. A TransactionCase proves the records are readable; it renders nothing, so it
// cannot catch a screen that filters itself in server-side action code or in an OWL loader -
// exactly the two traps this feature hit (the Students list is an ir.actions.server that
// re-domains itself by role, and the tutor grade matrix filters client-side).
//
// Driven by a guidance user who tutors nobody: every record below belongs to another teacher's
// tutees, so an empty list here is a real failure, not a missing fixture.
registry.category("web_tour.tours").add("ems_guidance_students_list", {
    test: true,
    url: "/odoo/action-ems.action_student_group_enrollment",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "The server-action-redirected students list loaded (it re-domains by role)",
        },
        // This DB carries 1000+ real students, paginated - search for the seeded one rather
        // than assuming it lands on the first page (same pattern as enrollment_proposal_tour).
        {
            trigger: ".o_searchview_input",
            content: "Search for the seeded student",
            run: "edit Test TOUR Student",
        },
        {
            trigger: ".o_searchview_input",
            content: "Confirm the search",
            run: "press Enter",
        },
        {
            // Deliberately no click: this list shows ems_current_enrollment_id as a many2one
            // column, and clicking a row here lands on the enrolment rather than the student.
            // The student form is covered by ems_guidance_student_file, opened by URL.
            trigger: ".o_data_cell[name='name']:contains('Test TOUR Student')",
            content: "A student this user does not tutor is listed, so the role's domain applies",
        },
    ],
});

// Opened straight at the student's form (the Python test builds the URL from the seeded id),
// so the tour asserts on the tabs themselves rather than on how one navigates to them.
registry.category("web_tour.tours").add("ems_guidance_student_file", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view",
            content: "The student form opened for a student this user does not tutor",
        },
        {
            trigger: ".o_notebook .nav-link[name='secretary']",
            content: "Open the Secretary tab",
            run: "click",
        },
        {
            trigger: ".o_notebook .tab-pane.active .o_field_widget[name='ems_authorization_ids'] .o_data_row",
            content: "The authorizations list has rows - it used to render empty, because the " +
                     "authorizations hang off the enrolment (a sale.order)",
        },
        {
            trigger: ".o_notebook .tab-pane.active .o_field_widget[name='benefit_ids'] .o_data_row",
            content: "The bonifications/exemptions list has rows too",
        },
        {
            trigger: ".o_notebook .nav-link[name='studies']",
            content: "Open the Studies tab, home of the academic history section",
            run: "click",
        },
        {
            trigger: ".o_notebook .tab-pane.active .o_field_widget[name='year_record_ids'] .o_data_row",
            content: "The frozen per-course academic history is readable",
        },
    ],
});

// Issue #465: the special educational needs typology is the guidance team's own subject, so on a
// student it does not tutor the student data block offers the editable dropdown, not the read-only
// badge every other teacher gets. Opened by URL, like ems_guidance_student_file.
registry.category("web_tour.tours").add("ems_guidance_special_needs", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .o_field_widget[name='special_needs'] select",
            content: "Set NEE-A",
            run: "selectByLabel NEE-A",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_form_button_save:not(:visible)",
            content: "Saved without an access error",
        },
    ],
});

// The widened scope of the same issue: the academic history is necessary information for the
// whole teaching community, so a plain teacher who tutors nobody reaches both the menu and the
// records behind it.
registry.category("web_tour.tours").add("ems_teacher_academic_history", {
    test: true,
    url: "/odoo/action-ems.action_year_record_list",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "The Academic history list loaded for a plain teacher",
        },
        {
            trigger: ".o_searchview_input",
            content: "Search for the seeded student's record",
            run: "edit Test TOUR Student",
        },
        {
            trigger: ".o_searchview_input",
            content: "Confirm the search",
            run: "press Enter",
        },
        {
            // The list is grouped by course by default, so the matching row starts collapsed.
            trigger: ".o_group_header",
            content: "Expand the course group",
            run: "click",
        },
        {
            trigger: ".o_data_cell[name='student_id']:contains('Test TOUR Student')",
            content: "A record of a student this teacher does not tutor is readable",
            run: "click",
        },
        {
            trigger: ".o_form_view",
            content: "Its form opens without an access error",
        },
    ],
});
