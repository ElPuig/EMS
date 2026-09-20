/** @odoo-module **/

import { registry } from "@web/core/registry";

// Smoke tour of the two screens phase 1 delivers: the controlled-document registry and the
// actions/agreements list. Structural selectors wherever possible (the .o_data_row of a list,
// the breadcrumb) instead of label text, so the tour does not depend on the session's language —
// see CLAUDE.md's "Tour tests and language". The seeded document registry is what the first half
// asserts on, so nothing has to be created before the tour starts.
registry.category("web_tour.tours").add("ems_quality_registry", {
    test: true,
    url: "/odoo/action-ems.action_quality_document",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row",
            content: "The document registry opens with its default 'Current' facet applied",
        },
        {
            trigger: ".o_searchview .o_facet_values",
            content: "The default facet is visible, so it can be removed with one click",
        },
        {
            trigger: ".o_list_view .o_data_row:first-child .o_data_cell",
            content: "Open the first controlled document",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_sheet",
            content: "The document form renders",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='version']",
            content: "The version field is on the form: this is what the footer of a generated document quotes",
        },
        {
            trigger: ".breadcrumb-item:first-child, .o_breadcrumb .o_back_button",
            content: "Back to the registry",
            run: "click",
        },
        {
            trigger: ".o_list_view",
            content: "Registry again",
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
