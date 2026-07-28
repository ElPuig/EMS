/** @odoo-module **/

import { registry } from "@web/core/registry";

// Both tours run against a document/student seeded by the Python test (never a real
// production record). Split into two registered tours, run sequentially from Python
// (see test_student_document_tour.py) rather than navigating mid-tour, matching the
// established pattern in withdrawal_tour.js.

// The actual review workflow lives under Academic Management > Student Documents —
// the only place Approve/Reject/Reset actually live (the per-student "Documentation"
// tab, covered by the second tour below, is read-only).
registry.category("web_tour.tours").add("ems_student_document_review", {
    test: true,
    url: "/odoo/action-ems.action_student_document",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Student documents list loaded",
        },
        {
            trigger: ".o_searchview_input",
            content: "Search for the seeded pending document's student",
            run: "edit Tour Doc Student",
        },
        {
            trigger: ".o_searchview_input",
            content: "Confirm the search",
            run: "press Enter",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('DNI / NIE') .fa-check",
            content: "Approve the DNI document from the list",
            run: "click",
        },
        {
            // The list defaults to the "Pending" filter (action context
            // search_default_pending) — once approved, the row simply drops out of it.
            trigger: ".o_list_view:not(:has(.o_data_row:contains('DNI / NIE')))",
            content: "Approved document no longer shown under the default Pending filter",
        },
        {
            trigger: ".o_list_view .o_data_row td:contains('Passport')",
            content: "Open the seeded pending Passport document",
            run: "click",
        },
        {
            // action_reject() has no confirmation step of its own — a single click
            // immediately flips the status, so the reason must be filled in first
            // (the object-type button auto-saves the dirty field before calling it).
            trigger: ".o_form_view .o_field_widget[name='rejection_reason'] input",
            content: "Fill in a rejection reason",
            run: "edit Tour: illegible scan",
        },
        {
            trigger: ".o_form_view button[name='action_reject']",
            content: "Reject it from the form",
            run: "click",
        },
        {
            trigger: ".o_form_view button[name='action_reset_to_pending']",
            content: "Reset-to-pending button now visible — confirms the status left 'pending'",
        },
    ],
});

// Read-only embed on the student's own form: confirm it renders the document (now
// rejected by the tour above) without crashing.
registry.category("web_tour.tours").add("ems_student_document_embed_view", {
    test: true,
    url: "/odoo/action-ems.action_student_kanban",
    steps: () => [
        {
            trigger: ".o_control_panel",
            content: "Educational Community loaded",
        },
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to list view",
            run: "click",
        },
        {
            trigger: ".o_searchview_input",
            content: "Search for the seeded student",
            run: "edit 0000 Tour Doc Student",
        },
        {
            trigger: ".o_searchview_input",
            content: "Confirm the search",
            run: "press Enter",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('Tour Doc Student')",
            content: "Open the seeded student",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Documentation')",
            content: "Open the Documentation tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='document_ids'] .o_data_row:contains('Rejected')",
            content: "Documentation tab renders the rejected document without crashing",
        },
    ],
});
