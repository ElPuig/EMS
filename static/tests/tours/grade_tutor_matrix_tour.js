/** @odoo-module **/

import { registry } from "@web/core/registry";
import { editGradeMatrixCell } from "@ems/../tests/tours/grade_matrix_helpers";

// ems.grade_tutor_matrix ("Planning and Grading > Grades > Evaluation for tutors") is a second
// bespoke OWL client action, structurally unrelated to the standard list/form views - like the
// daily roll-call screen (ems_attendance_session_view), a crash here would fail the whole
// screen, not just a widget. It had zero tour coverage before this. Renders one student at a
// time (paginated), aggregating every subject the tutor's group has an open grade session for.
registry.category("web_tour.tours").add("ems_grade_tutor_matrix_entry", {
    test: true,
    url: "/odoo/action-ems.action_grade_tutor_matrix",
    steps: () => [
        {
            trigger: ".o_grade_tutor_pager",
            content: "The tutor matrix loaded with the first (only) tutored group/student",
        },
        {
            trigger: ".o_grade_tutor_name:contains('Alpha')",
            content: "First student (sorted by lastname) is shown",
        },
        editGradeMatrixCell(".o_grade_tutor tbody tr:first-child td.o_grade_matrix_cell", "7"),
        {
            trigger: ".o_grade_matrix_toolbar button:not(:disabled)",
            content: "Apply changes is enabled now that the buffer is dirty",
            run: "click",
        },
        {
            trigger: ".o_grade_tutor tbody tr:first-child td.o_grade_matrix_cell span:contains('7')",
            content: "The entered score persisted and re-rendered after apply",
        },
        {
            trigger: ".o_grade_tutor_navbtn:not(:disabled):has(.fa-chevron-right)",
            content: "Page to the second student",
            run: "click",
        },
        {
            trigger: ".o_grade_tutor_name:contains('Beta')",
            content: "Second student is now shown - pagination renders correctly too",
        },
    ],
});
