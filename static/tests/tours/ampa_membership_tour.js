/** @odoo-module **/

import { registry } from "@web/core/registry";
import { searchStudent, studentCell, studentRow } from "@ems/../tests/tours/student_list_helpers";

// Issue #820: a tutor lists their students with and without AMPA membership.
registry.category("web_tour.tours").add("ems_ampa_membership", {
    url: "/odoo/action-ems.action_student_kanban",
    steps: () => [
        { trigger: ".o_kanban_view", content: "The Students kanban opens" },
        { trigger: ".o_switch_view.o_list", content: "Switch to the list", run: "click" },
        ...searchStudent("Ampatest"),
        {
            trigger: `${studentRow("Ampatest Socia")} .o_data_cell[name='ems_ampa_member']:contains('Yes')`,
            content: "The member reads Yes",
        },
        {
            trigger: `${studentRow("Ampatest Nosocia")} .o_data_cell[name='ems_ampa_member']:contains('No')`,
            content: "The non-member reads No",
        },
        {
            trigger: `.o_list_view:not(:has(${studentRow("Ampatest Altra")}))`,
            content: "Another tutor's student stays out of 'My students'",
        },
        { trigger: ".o_searchview_dropdown_toggler", content: "Open the filters", run: "click" },
        {
            trigger: ".o_filter_menu .o-dropdown-item:contains('AMPA member'):not(:contains('Not'))",
            content: "Filter the AMPA members",
            run: "click",
        },
        {
            trigger: `.o_list_view:not(:has(${studentRow("Ampatest Nosocia")})) ${studentCell("Ampatest Socia")}`,
            content: "Only the member is left",
            run: "click",
        },
        {
            trigger: ".o_form_view .badge.o_ems_ampa:contains('Yes')",
            content: "The student form shows the AMPA badge",
        },
        { trigger: "body:not(:has(.o_error_dialog))", content: "No client-side error" },
    ],
});
