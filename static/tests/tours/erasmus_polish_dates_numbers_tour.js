/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #778 - dates without a time and blank zeros. Records seeded by
// tests/test_erasmus_polish_dates_numbers_tour.py.

const CALL = "Test Erasmus Call";
const DAY_ONLY = ":contains('/'):not(:contains(':'))";

function assertHourWithoutSeconds() {
    if (!/\d{1,2}:\d{2}(\s?[AP]M)?$/.test(this.anchor.value)) {
        throw new Error(`Expected an hour without seconds, got "${this.anchor.value}"`);
    }
}

function assertEmptyInput() {
    if (this.anchor.value !== "") {
        throw new Error(`Expected an empty input, got "${this.anchor.value}"`);
    }
}

// 1.8, 2.5: the list shows the day; the form's editable deadline keeps its hour, without seconds.
registry.category("web_tour.tours").add("ems_erasmus_call_dates", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_call",
    steps: () => [
        {
            trigger: `.o_list_view .o_data_row:contains('${CALL}') td[name='date_close']${DAY_ONLY}`,
            content: "The list shows the closing day alone",
        },
        {
            trigger: `.o_list_view .o_data_row:contains('${CALL}') td[name='name']`,
            content: "Open the call",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='date_close'] input",
            content: "The editable deadline keeps the hour that decides it",
            run: assertHourWithoutSeconds,
        },
    ],
});

// 3.14: stamps show the day; an offer's deadline keeps its hour, in the list and in the form.
registry.category("web_tour.tours").add("ems_erasmus_offer_dates", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_offer",
    steps: () => [
        {
            trigger: `.o_list_view .o_data_row td[name='offer_date']${DAY_ONLY}`,
            content: "When it was offered: the day alone",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='deadline']:contains(':')",
            content: "The deadline keeps its hour",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='deadline']",
            content: "Open the offer",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='deadline']:contains(':')",
            content: "The form keeps it too",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='offer_date']:contains('/'):not(:contains(':'))",
            content: "The offer's date, the day alone",
        },
    ],
});

// 13.8: no limit and any duration are an empty cell, not a 0, and can still be typed in.
registry.category("web_tour.tours").add("ems_erasmus_rate_blank_zero", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_support_rate",
    steps: () => [
        {
            trigger: ".o_list_view .o_group_header:contains('2098') + .o_data_row td[name='band_to']:empty",
            content: "No limit: the cell is empty",
        },
        {
            trigger: ".o_list_view .o_group_header:contains('2098') + .o_data_row td[name='min_days']",
            content: "Edit the row",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_selected_row td[name='band_to'] input[placeholder]",
            content: "While editing, the placeholder says what empty means",
            run: assertEmptyInput,
        },
        {
            trigger: ".o_list_view .o_selected_row td[name='min_days'] input",
            content: "A real value can be typed",
            run: "edit 5",
        },
        {
            trigger: ".o_list_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_group_header:contains('2098') + .o_data_row td[name='min_days']:contains('5')",
            content: "The value stays",
        },
    ],
});

// 12.12: people reached, unknown: empty in the list and in the form.
registry.category("web_tour.tours").add("ems_erasmus_diffusion_blank_zero", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_diffusion",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row:contains('Test Diffusion Session') td[name='recipient_count']:empty",
            content: "Unknown: the cell is empty",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('Test Diffusion Session') td[name='name']",
            content: "Open the action",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='recipient_count'] input[placeholder]",
            content: "The form too",
            run: assertEmptyInput,
        },
        {
            trigger: ".o_form_view .o_field_widget[name='recipient_count'] input",
            content: "The figure, once known",
            run: "edit 25",
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

// 13.2: a course with no staff figures: empty cells.
registry.category("web_tour.tours").add("ems_erasmus_history_blank_zero", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_quality_history",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row:contains('2001-2002') td[name='student_applicants']:contains('7')",
            content: "A real figure shows",
        },
        {
            // Issue #810: the staff columns are hidden at first, shown from the columns menu.
            trigger: ".o_list_view:not(:has(th[data-name='staff_target'])) .o_optional_columns_dropdown_toggle",
            content: "Open the optional columns",
            run: "click",
        },
        {
            trigger: ".o-dropdown--menu input[name='staff_applicants']",
            content: "Show the staff applicants",
            run: "click",
        },
        {
            trigger: ".o-dropdown--menu input[name='staff_target']",
            content: "Show the eligible staff",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('2001-2002') td[name='staff_target']:empty",
            content: "No staff data: the cell is empty",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('2001-2002') td[name='staff_applicants']:empty",
            content: "Likewise for the applicants",
        },
    ],
});
