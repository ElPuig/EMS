/** @odoo-module **/

import { registry } from "@web/core/registry";

// Smoke tour of the Quality app's reading screens: the embedded process map and the three
// configuration lists (processes, procedures, documents). Structural selectors wherever possible
// (the .o_data_row of a list, the iframe) instead of label text, so the tour does not depend on the
// session's language - see CLAUDE.md's "Tour tests and language". The seeded structure is what
// it asserts on, so nothing has to be created before the tour starts.
registry.category("web_tour.tours").add("ems_quality_registry", {
    test: true,
    url: "/odoo/action-ems.action_quality_process_map",
    steps: () => [
        {
            trigger: ".o_quality_process_map iframe.o_quality_process_map_frame[src*='pub?embedded=true']",
            content: "The process map embeds the published document configured in the settings",
        },
        {
            trigger: ".o_quality_process_map a[target='_blank']",
            content: "And offers to open it in a new tab",
        },
        {
            trigger: "body",
            content: "Go to the documents",
            run: () => { window.location.href = "/odoo/action-ems.action_quality_document"; },
            expectUnloadPage: true,
        },
        {
            trigger: ".o_list_view .o_group_header",
            content: "Documents open grouped by process",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell[name='name']",
            content: "Edit a document in place, the list is editable",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_selected_row .o_field_widget[name='url'] input",
            content: "Its link is editable right there",
        },
        {
            trigger: ".o_list_button_discard",
            content: "Leave it untouched",
            run: "click",
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
            trigger: ".modal .o_form_button_cancel, .modal footer .btn-secondary",
            content: "Close it",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal))",
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
            trigger: ".o_list_view .o_data_row:first-child .o_data_cell[name='code']",
            content: "Open a process",
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
