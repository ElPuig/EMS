/** @odoo-module **/

import { registry } from "@web/core/registry";
import { searchStudent, studentCell, studentRow } from "@ems/../tests/tours/student_list_helpers";

// Issue #421: the Students action opens with a second default facet ("My students") that
// scopes the list to the groups the logged-in teacher actually teaches or tutors. Runs as a
// seeded teacher (not admin, who teaches nothing and would therefore see the inert branch),
// so this is the only place the restricted path is exercised in a real browser.
registry.category("web_tour.tours").add("ems_student_my_groups", {
    test: true,
    url: "/odoo/action-ems.action_student_kanban",
    steps: () => [
        {
            trigger: ".o_searchview_facet:contains('My students')",
            content: "The 'My students' facet is applied by default",
        },
        {
            trigger: ".o_searchview_facet:contains('Students')",
            content: "...on top of the pre-existing 'Students' facet, not instead of it",
        },
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to list view",
            run: "click",
        },
        ...searchStudent("My Groups"),
        {
            trigger: `.o_list_view ${studentCell("0000 My Groups Own Student")}`,
            content: "The student of the teacher's own group is listed",
        },
        {
            trigger: `.o_list_view:not(:has(${studentRow("0001 My Groups Other Student")}))`,
            content: "A student of a group this teacher does not teach is filtered out",
        },
        {
            trigger: ".o_searchview_facet:contains('My students') .o_facet_remove",
            content: "Remove the facet: a teacher must always be able to see every student",
            run: "click",
        },
        {
            trigger: `.o_list_view ${studentCell("0001 My Groups Other Student")}`,
            content: "Every student is visible again once the facet is cleared",
        },
        {
            trigger: "body:not(:has(.o_error_dialog))",
            content: "No client-side error along the way",
        },
    ],
});
