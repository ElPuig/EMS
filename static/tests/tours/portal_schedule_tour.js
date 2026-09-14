/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #453: the student's weekly schedule on the portal's Attendance card. Structural selectors
// only, so the portal user's language doesn't matter.
registry.category("web_tour.tours").add("ems_portal_schedule_render", {
    test: true,
    url: "/my/asistencia",
    steps: () => [
        {
            trigger: ".o_ems_portal_schedule .table-responsive table.gs-table .gs-cell-label",
            content: "The weekly grid rendered with the student's class",
        },
        {
            trigger: ".o_ems_portal_schedule .gs-summary-table",
            content: "The Subject/Teacher(s) table rendered",
        },
        {
            trigger: ".o_ems_portal_schedule a.o_ems_portal_schedule_pdf[href='/my/asistencia/pdf']",
            content: "The PDF download button is shown",
        },
    ],
});
