/** @odoo-module **/

import { registry } from "@web/core/registry";
import { checkActions, noActions } from "@ems/../tests/tours/actions_dropdown_helpers";

// Issue #524: where a tutor finds "Print student card". The PDF itself is covered by
// TestStudentCard (a download can't be asserted from a tour), so no entry is clicked.

// The students list: an entry of the selection's Actions (cog) menu.
registry.category("web_tour.tours").add("ems_student_card_list", {
    test: true,
    url: "/odoo/action-ems.action_student_kanban",
    steps: () => [
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to list view",
            run: "click",
        },
        {
            // The tutor's "My students" facet leaves only their own student; the list shows the
            // first and last names in separate columns.
            trigger: ".o_data_row:has(.o_data_cell:contains('TSCT')) .o_list_record_selector",
            content: "Select the tutor's student",
            run: "click",
        },
        {
            trigger: ".o_cp_action_menus button:has(.fa-cog)",
            content: "Open the list's Actions (cog) menu",
            run: "click",
        },
        {
            trigger: ".o-dropdown--menu .o_menu_item:contains('Print student card')",
            content: "The tutor can print the selected students' cards",
        },
    ],
});

// The tutor's own student's form, and their group's: an entry of the Actions dropdown (and, on the
// student's form, "Revoke student card").
registry.category("web_tour.tours").add("ems_student_card_student_form", {
    test: true,
    steps: () => [
        ...checkActions({ offered: ["action_print_student_card", "action_revoke_student_card"] }, "The tutor's student: the card is offered, and can be revoked"),
    ],
});

registry.category("web_tour.tours").add("ems_student_card_group_form", {
    test: true,
    steps: () => [
        ...checkActions({ offered: ["action_print_student_cards"] }, "The tutor's group: the cards are offered"),
    ],
});

// Another tutor's group: nothing to print, and no other entry applies, so no dropdown at all.
registry.category("web_tour.tours").add("ems_student_card_foreign_group_form", {
    test: true,
    steps: () => [
        noActions("Another tutor's group: the cards are not offered"),
    ],
});
