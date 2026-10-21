/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #654: the Head of Studies opens Academic management > Enrollment > Enrollments and reads
// an enrollment outside their chain of command, in the list, the kanban and the form.
// Opened by URL on the action (see test_enrollment_head_of_studies_tour.py).
registry.category("web_tour.tours").add("ems_enrollment_head_of_studies", {
    test: true,
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row:contains('0000 HSET Enrollment Student')",
            content: "The enrollment is listed",
        },
        {
            trigger: ".o_switch_view.o_kanban",
            content: "Switch to the kanban view",
            run: "click",
        },
        {
            trigger: ".o_kanban_view .o_kanban_record:contains('0000 HSET Enrollment Student')",
            content: "The enrollment shows in the kanban",
        },
        {
            trigger: ".o_switch_view.o_list",
            content: "Back to the list",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('0000 HSET Enrollment Student') td[name='partner_id']",
            content: "Open the enrollment",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_breadcrumb:contains('/HSET/')",
            content: "The enrollment's form opens",
        },
    ],
});

// Issue #654: any other list of Academic management > Enrollment and its Configuration section
// opens for the Head of Studies (a crash fails the tour through the console error).
registry.category("web_tour.tours").add("ems_enrollment_head_of_studies_list", {
    test: true,
    steps: () => [
        {
            trigger: ".o_list_view .o_list_renderer",
            content: "The list renders",
        },
    ],
});
