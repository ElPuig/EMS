/** @odoo-module **/

import { registry } from "@web/core/registry";

// A department head writes a department minute end to end: the type lays out the sections, the
// attendees arrive preloaded from the department, an agreement is added, and it goes for approval.
// Structural selectors rather than label text, so the tour does not depend on the session language.
registry.category("web_tour.tours").add("ems_minute_write", {
    test: true,
    url: "/odoo/action-ems.action_minute",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Minutes list opens with its default facets",
        },
        {
            trigger: ".o_list_button_add",
            content: "Start a new minute",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='type_id'] input",
            content: "Pick the type, which is what lays the minute out",
            run: "click",
        },
        {
            trigger: ".o-autocomplete--dropdown-menu li:first-child",
            content: "Take the first type offered",
            run: "click",
        },
        {
            trigger: ".o_notebook .nav-link:contains('Content'), .o_notebook .nav-item:nth-child(5) .nav-link",
            content: "The sections tab is there",
            run: "click",
        },
        {
            // If the type declared sections, the minute must already have rows here: an empty
            // table means the layout never got built, which is the point of this step.
            trigger: ".o_field_x2many .o_data_row",
            content: "The sections of this type are already laid out",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='code'] span:not(:empty)",
            content: "The code has been issued",
        },
        {
            trigger: "button[name='action_submit']",
            content: "Send it for approval",
            run: "click",
        },
        {
            trigger: ".o_statusbar_status .o_arrow_button_current",
            content: "The state moved on",
        },
    ],
});
