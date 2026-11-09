/** @odoo-module **/

import { registry } from "@web/core/registry";
import { openActions } from "@ems/../tests/tours/actions_dropdown_helpers";

// Issue #779 - labels with some behaviour of their own. Records seeded by
// tests/test_erasmus_polish_labels_tour.py.

function assertDeclaredPlaceholder() {
    const first = this.anchor.options[0].textContent;
    if (!first.includes("Correct, as declared")) {
        throw new Error(`Expected the placeholder, got "${first}"`);
    }
}

// 3.9: points with their maximum, no needless decimals.
registry.category("web_tour.tours").add("ems_erasmus_student_points", {
    test: true,
    steps: () => [
        {
            trigger: ".o_notebook a.nav-link[name='scoring']",
            content: "Open the scoring",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='score_d']:contains('10 / 10')",
            content: "Fewer opportunities, over its maximum",
        },
        {
            trigger: ".o_field_widget[name='score_e']:contains('5 / 5')",
            content: "First mobility, over its maximum",
        },
        {
            trigger: ".o_field_widget[name='score_total']:contains('/ 100')",
            content: "The total, over 100",
        },
    ],
});

// 6.3, 7.4, 7.5: the correction fields say what empty means, and the commission's ratings have
// a title, no repeated person and their maximum.
registry.category("web_tour.tours").add("ems_erasmus_staff_labels", {
    test: true,
    steps: () => [
        {
            trigger: ".o_notebook a.nav-link[name='staff_scoring']",
            content: "Open the scoring",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='seniority'] select",
            content: "Empty means the declaration is right",
            run: assertDeclaredPlaceholder,
        },
        {
            trigger: ".o_field_widget[name='last_staff_mobility'] select",
            content: "Likewise the last mobility",
            run: assertDeclaredPlaceholder,
        },
        {
            trigger: ".o_field_widget[name='language_level'] select",
            content: "Likewise the language certificate",
            run: assertDeclaredPlaceholder,
        },
        {
            trigger: ".o_field_widget[name='score_seniority']:contains('/ 2')",
            content: "A criterion with its maximum",
        },
        {
            trigger: ".o_field_widget[name='plan_rating_ids'] table:not(:has(th[data-name='evaluator_id']))",
            content: "The ratings no longer repeat the person",
        },
        {
            trigger: ".o_field_widget[name='plan_rating_ids'] .o_data_row td[name='score']:contains('/ 2')",
            content: "A rating over its maximum",
        },
    ],
});

// 13.8: short headers that read in full.
registry.category("web_tour.tours").add("ems_erasmus_rate_headers", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_support_rate",
    steps: () => [
        { trigger: ".o_list_view th[data-name='band_from']:contains('From')", content: "From" },
        { trigger: ".o_list_view th[data-name='band_to']:contains('Up to')", content: "Up to" },
        { trigger: ".o_list_view th[data-name='min_days']:contains('Min. days')", content: "Minimum days" },
    ],
});

// 13.2: the list stays readable; the whole line, source included, opens in a form.
registry.category("web_tour.tours").add("ems_erasmus_history_form", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_quality_history",
    steps: () => [
        {
            trigger: ".o_list_view:not(:has(th[data-name='source']))",
            content: "The source is hidden in the list",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('2001-2002') td[name='course_name']",
            content: "Open the line",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='source']",
            content: "The source reads in full",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='staff_target'] input",
            content: "Type a figure",
            run: "edit 9",
        },
        {
            trigger: ".o_form_view .o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_saved",
            content: "Saved",
        },
    ],
});

// 10.13: each download says what it gives.
registry.category("web_tour.tours").add("ems_erasmus_project_downloads", {
    test: true,
    steps: () => [
        openActions(),
        {
            trigger: ".o_ems_actions_menu button[name='action_export']:contains('Download the project archive (ZIP)')",
            content: "The archive",
        },
        {
            trigger: ".o_ems_actions_menu button[name='action_export_economy']:contains('Download the economy (Excel)')",
            content: "The accounts",
        },
    ],
});
