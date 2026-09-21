/** @odoo-module **/

import { registry } from "@web/core/registry";

// Smoke tour of the Quality app's reading screens: the process map (the form of the document
// marked as such) and the three configuration screens. It checks the read-only default and the
// 'Edit' button of those forms. Structural selectors wherever possible instead of label text, so
// the tour does not depend on the session's language - see CLAUDE.md's "Tour tests and language".
registry.category("web_tour.tours").add("ems_quality_registry", {
    test: true,
    url: "/odoo/action-ems.action_quality_process_map_open",
    steps: () => [
        {
            trigger: ".o_form_view iframe.o_quality_document_preview[src$='/preview']",
            content: "The process map shows the document from the preview address derived from its link",
        },
        {
            trigger: ".o_form_view .o_form_statusbar button[name='action_open_document']",
            content: "And offers to open it in a new tab",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='name']:not(:has(input))",
            content: "The form opens read-only",
        },
        {
            trigger: ".o_form_view .o_quality_edit_button",
            content: "Edit",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='url'] input",
            content: "Editing unlocks the fields, the link among them",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='name'] input",
            content: "Change something",
            run: "edit Tour change",
        },
        {
            trigger: ".o_form_button_cancel",
            content: "Discard",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_quality_edit_button",
            content: "Discarding goes back to read-only",
        },
        {
            trigger: "body",
            content: "Go to the documents",
            run: () => { window.location.href = "/odoo/action-ems.action_quality_document"; },
            expectUnloadPage: true,
        },
        {
            trigger: ".o_control_panel button.o_quality_load_links",
            content: "Open the wizard that loads links in one go",
            run: "click",
        },
        {
            trigger: ".modal .o_form_view .o_field_widget[name='file_data']",
            content: "The link loader opens",
        },
        {
            trigger: ".modal footer .btn-secondary",
            content: "Close it",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal)) .o_list_view .o_group_header",
            content: "Documents open grouped by process",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell[name='name']",
            content: "Open a document",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_quality_edit_button",
            content: "Its form opens read-only too, with 'Edit' in the header",
        },
        {
            trigger: "body",
            content: "Go to the procedures",
            run: () => { window.location.href = "/odoo/action-ems.action_quality_procedure"; },
            expectUnloadPage: true,
        },
        {
            trigger: ".o_list_view .o_group_header",
            content: "Procedures grouped by process",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell[name='code']",
            content: "Open a procedure",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_quality_edit_button",
            content: "Read-only, with 'Edit'",
        },
        {
            trigger: ".o_form_view iframe.o_quality_document_preview[src$='/preview']",
            content: "The procedure's first tab is its own sheet",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link[name='documents']",
            content: "Its documents are one tab further",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='document_ids']",
            content: "The procedure form lists its documents",
        },
        {
            trigger: "body",
            content: "Go to the processes",
            run: () => { window.location.href = "/odoo/action-ems.action_quality_process"; },
            expectUnloadPage: true,
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell[name='code']",
            content: "Open a process",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_quality_edit_button",
            content: "Read-only, with 'Edit'",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link.active[name='document'], .o_form_view .o_notebook .nav-item:first-child .nav-link.active",
            content: "The first tab is the process's own document",
        },
        {
            trigger: ".o_form_view iframe.o_quality_document_preview[src$='/preview']",
            content: "Shown from its link, like the process map",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link[name='procedures']",
            content: "Its procedures are one tab further",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='procedure_ids']",
            content: "The process form lists its procedures",
        },
    ],
});

// Second tour, deliberately separate: it writes, so it must not leave the registry tour's
// assertions depending on what it created.
registry.category("web_tour.tours").add("ems_quality_action_followup", {
    test: true,
    url: "/odoo/action-ems.action_quality_action",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Actions and agreements list",
        },
        {
            trigger: ".o_list_button_add",
            content: "Create an agreement",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='name'] input",
            content: "Name it",
            run: "edit Tour agreement",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='department_id'] input",
            content: "Give it a scope, which is what its code is numbered against",
            run: "click",
        },
        {
            trigger: ".o-autocomplete--dropdown-menu li:first-child",
            content: "Take the first department offered",
            run: "click",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            // The code is issued by sequence on create: if it is empty here, the sequence helper
            // did not run, which is the failure this step exists to catch.
            trigger: ".o_form_view .o_field_widget[name='code'] span:not(:empty)",
            content: "The code has been issued",
        },
        {
            trigger: ".o_form_view .o_statusbar_status .o_arrow_button_current",
            content: "The state shows, derived from the (still empty) follow-up",
        },
    ],
});
