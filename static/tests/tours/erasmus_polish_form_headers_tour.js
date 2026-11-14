/** @odoo-module **/

import { registry } from "@web/core/registry";
import { clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

// Issues #783 and #784 - empty lists, help texts, form headers and smart buttons. Records seeded by
// tests/test_erasmus_polish_form_headers_tour.py; structural selectors (field and button names).

const STUDENT = "Erasmus Test Student";

function openTab(name) {
    return {
        trigger: `.o_notebook a.nav-link[name='${name}']`,
        content: `The ${name} tab`,
        run: "click",
    };
}

// 2.7: a number on every button of the call; the ranking stays after the definitive resolution.
registry.category("web_tour.tours").add("ems_erasmus_form_headers_call", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view button[name='action_view_mobilities'] .o_stat_value:contains('2')",
            content: "The mobilities button counts them",
        },
        {
            // Odoo puts the buttons that do not fit in its own "More" dropdown.
            trigger: ".o-form-buttonbox .o_button_more",
            content: "The rest of the buttons",
            run: "click",
        },
        {
            trigger: ".o-dropdown--menu button[name='action_view_ranking'] .o_stat_value",
            content: "The ranking, with its number, after the definitive resolution too",
        },
        {
            trigger: ".o-dropdown--menu button[name='action_view_resolutions'] .o_stat_value",
            content: "The resolutions, counted",
        },
    ],
});

// 3.4, 3.11: what decides the application on top; answers and documents in one tab.
registry.category("web_tour.tours").add("ems_erasmus_form_headers_application", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .oe_title + .o_group .o_field_widget[name='requirements_check']",
            content: "The requirements on top",
        },
        {
            trigger: ".o_form_view .o_group .o_field_widget[name='rank']",
            content: "And the rank",
        },
        {
            trigger: ".o_form_view .o_notebook:not(:has(a.nav-link[name='answers']))",
            content: "No separate Answers tab",
        },
        openTab("documents"),
        {
            trigger: ".o_notebook .tab-pane.active:has(.o_field_widget[name='image_consent']):has(.o_field_widget[name='document_ids'])",
            content: "The answers and the documents together",
        },
    ],
});

// 5.4, 8.5, 5.6, 8.6, 5.9: short breadcrumb, the application as a button, the record as a bar,
// the commitment letter in one line.
registry.category("web_tour.tours").add("ems_erasmus_form_headers_mobility", {
    test: true,
    steps: () => [
        {
            trigger: `.o_breadcrumb .active:contains('${STUDENT}'):not(:contains('Test Erasmus Call'))`,
            content: "The breadcrumb says who",
        },
        {
            trigger: ".o_form_view button[name='action_open_application']",
            content: "The application, as a button",
        },
        {
            trigger: ".o_form_view .o_inner_group:first:not(:has(.o_field_widget[name='rank']))",
            content: "No rank on the mobility",
        },
        openTab("documents"),
        {
            trigger: ".o_field_widget[name='record_done'] .o_progressbar",
            content: "The record as one bar",
        },
        {
            trigger: ".o_form_view:not(:has(.o_field_widget[name='eu_survey_state']:visible))",
            content: "No EU Survey before the stay ends",
        },
        openTab("commitment"),
        {
            trigger: ".o_field_widget[name='commitment_status']:not(:empty)",
            content: "Whether the letter is signed, in one line",
        },
    ],
});

// 4.8: the time left to answer.
registry.category("web_tour.tours").add("ems_erasmus_form_headers_offers", {
    test: true,
    steps: () => [
        {
            trigger: ".o_list_view thead th:contains('Time left')",
            content: "A column with how long is left to answer (filled in while pending)",
        },
    ],
});

// 10.5, 10.7, 10.10: the Documentation tab explains itself and keeps the retention.
registry.category("web_tour.tours").add("ems_erasmus_form_headers_project", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .oe_title + .o_group:not(:has(.o_field_widget[name='keep_until']))",
            content: "No retention on top of the project",
        },
        openTab("documents"),
        {
            trigger: ".o_notebook .tab-pane.active .fa-info-circle",
            content: "A line says what goes here",
        },
        {
            trigger: ".o_notebook .tab-pane.active .o_field_widget[name='retention_hold']",
            content: "The retention with the documents",
        },
    ],
});

// 13.5, 13.7: the host entity's mobilities; its notes say who reads them.
registry.category("web_tour.tours").add("ems_erasmus_form_headers_host", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view button[name='action_view_erasmus_mobilities'] .o_stat_value:contains('1')",
            content: "The mobilities it has hosted",
        },
        {
            trigger: ".o_form_view:not(:has(button[name='schedule_meeting']))",
            content: "No meetings button on a host entity",
        },
        openTab("internal_notes"),
        {
            trigger: ".o_notebook .tab-pane.active .fa-eye",
            content: "Who reads the notes",
        },
    ],
});

// 9.4, 9.15: the dates and who pays.
registry.category("web_tour.tours").add("ems_erasmus_form_headers_group", {
    test: true,
    steps: () => [
        openTab("expenses"),
        {
            trigger: ".o_field_widget[name='travel_paid_by'] input[data-value='centre']:checked",
            content: "Who pays the travel and accommodation, asked in positive",
        },
        {
            trigger: ".o_field_widget[name='prefinancing_percent']",
            content: "The pocket money percentage",
        },
    ],
});

// P01, P02, P07: the teacher's staff calls, the call's information and the upload dialog.
registry.category("web_tour.tours").add("ems_erasmus_form_headers_teacher", {
    test: true,
    steps: () => [
        {
            trigger: ".o_list_view:not(:has(th[data-name='is_accepting']))",
            content: "No 'accepts applications' column",
        },
        {
            trigger: ".o_list_view .o_data_row:first .o_data_cell[name='name']",
            content: "Open the call",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_horizontal_separator",
            content: "The information for applicants has its title",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='description']:contains('Tour information for applicants')",
            content: "And the team's text",
        },
        {
            trigger: ".o_form_view:not(:has(.o_field_widget[name='is_accepting']:visible))",
            content: "No grey checkbox",
        },
        ...clickAction("action_staff_apply", "Open my application"),
        openTab("documents"),
        {
            trigger: ".o_field_widget[name='document_ids'] .o_data_row:first button[name='action_staff_upload']",
            content: "Hand in a document",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='attachment_ids']",
            content: "The upload button",
        },
        {
            trigger: ".modal:not(:has(label.o_form_label:contains('Files')))",
            content: "No label repeating the button",
        },
        {
            trigger: ".modal-footer .btn-secondary",
            content: "Close",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal))",
        },
    ],
});
