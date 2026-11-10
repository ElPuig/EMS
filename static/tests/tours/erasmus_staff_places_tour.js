/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #772. Records seeded by tests/test_erasmus_staff_places_tour.py.

registry.category("web_tour.tours").add("ems_erasmus_staff_places_per_project", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .alert-warning:contains('places accepted without a project')",
            content: "Note 7.1: an accepted place without a project is warned",
        },
        {
            trigger: ".o_form_view .o_notebook:not(:has(a.nav-link[name='modalities'])) a.nav-link[name='project_places']",
            content: "No modalities: the places per project",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='project_place_ids'] .o_data_row:contains('2096-VET') td[name='assigned_count']:contains('1')",
            content: "Each project's places and how many are assigned",
        },
        {
            trigger: ".o_form_view button[name='action_view_mobilities']",
            content: "The call's mobilities",
            run: "click",
        },
        {
            trigger: ".o_list_view table:not(:has(th[data-name='modality_id'])) .o_data_row:has(td[name='project_id']:contains('2096-VET')) td[name='partner_id']",
            content: "The list shows the project's short name, and no modality",
        },
        {
            trigger: ".o_cp_switch_buttons .o_switch_view.o_kanban",
            content: "The kanban too",
            run: "click",
        },
        {
            trigger: ".o_kanban_record:contains('Erasmus Staff 1')",
            content: "Open the mobility with a project",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='project_places']:contains('2096-VET: 0 of 1 places left')",
            content: "The places left of the project",
        },
        {
            trigger: ".o_form_view:not(:has(.o_field_widget[name='modality_id']))",
            content: "A staff mobility has no modality",
        },
    ],
});
