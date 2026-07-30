/** @odoo-module **/

import { registry } from "@web/core/registry";

// action_ems_enrollments (sale.order, the day-to-day "matrícula" screen used by secretary/
// admin) had zero browser coverage despite extensive backend TransactionCase coverage
// (test_enrollment_header.py, test_enrollment_benefit.py, etc.) - none of that touches the
// heavily xpath-customized native sale.order form (EMS-specific fields injected via many
// xpaths, three added/renamed notebook pages) in an actual browser. This tour opens a
// pre-seeded draft enrollment, walks every EMS-added tab (Enrollment Items / Authorizations /
// Payment) to confirm none of them crash on render, and does one real edit+save (the `shift`
// field) to prove the form is genuinely interactive, not just static markup.
registry.category("web_tour.tours").add("ems_enrollment_form_tabs", {
    test: true,
    url: "/odoo/action-ems.action_ems_enrollments",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Enrollments list loaded",
        },
        {
            trigger: ".o_searchview_input",
            content: "Search for the seeded enrollment's student",
            run: "edit Enrollment Tour Student",
        },
        {
            trigger: ".o_searchview_input",
            content: "Confirm the search",
            run: "press Enter",
        },
        {
            trigger: ".o_list_view .o_data_row td:contains('Enrollment Tour Student')",
            content: "Open the seeded enrollment",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='ems_study_id'] input",
            content: "Enrollment form loaded with the EMS study field",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='shift'] select",
            content: "Switch the shift from Morning to Afternoon",
            run: "selectByLabel Afternoon",
        },
        {
            trigger: ".o_notebook .nav-link:contains('Enrollment Items')",
            content: "Open the Enrollment Items tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='order_line'] .o_data_row td:contains('Test Enrollment Tour Fee')",
            content: "The seeded fee line renders",
        },
        {
            trigger: ".o_notebook .nav-link:contains('Authorizations')",
            content: "Open the Authorizations tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='ems_authorization_ids']",
            content: "The (empty) authorizations list renders without crashing",
        },
        {
            trigger: ".o_notebook .nav-link:contains('Payment')",
            content: "Open the Payment tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='payment_term_id']",
            content: "The payment plan fields render",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save the shift change",
            run: "click",
        },
        {
            trigger: ".o_form_button_save:not(:visible)",
            content: "Save completed",
        },
    ],
});
