/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #781 - the lists used to value applications. Records seeded by
// tests/test_erasmus_polish_selection_lists_tour.py.

const CALL = "Test Erasmus Call";

function openPreparationDocuments() {
    return [
        {
            trigger: ".o_notebook a.nav-link[name='mobility_block']",
            content: "The mobility block",
            run: "click",
        },
        {
            trigger: ".o_notebook a.nav-link[name='preparation_documents']",
            content: "Its documents",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='preparation_document_ids'] table:not(:has(th[data-name='sign_guardian']))",
            content: "No signature columns in the list",
        },
        {
            trigger: ".o_field_widget[name='preparation_document_ids'] .o_data_row:contains('Tour Agreement') td[name='name']",
            content: "Open the line",
            run: "click",
        },
    ];
}

// 2.2: five columns, the rest when opening the line, with the signatures that apply to a student.
registry.category("web_tour.tours").add("ems_erasmus_list_documents_student", {
    test: true,
    steps: () => [
        ...openPreparationDocuments(),
        {
            trigger: ".modal .o_field_widget[name='sign_guardian']",
            content: "A student's document can ask for the legal guardian",
        },
        {
            trigger: ".modal .o_field_widget[name='sign_tutor']",
            content: "And for the centre's tutor",
        },
        {
            trigger: ".modal .o_form_button_cancel",
            content: "Close",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal))",
            content: "Closed",
        },
    ],
});

// 6.5: a teacher has neither.
registry.category("web_tour.tours").add("ems_erasmus_list_documents_staff", {
    test: true,
    steps: () => [
        ...openPreparationDocuments(),
        {
            trigger: ".modal .o_field_widget[name='sign_participant']",
            content: "The line is open",
        },
        {
            trigger: ".modal .o_form_sheet:not(:has(.o_field_widget[name='sign_guardian'])):not(:has(.o_field_widget[name='sign_tutor']))",
            content: "No legal guardian nor centre's tutor for staff",
        },
        {
            trigger: ".modal .o_form_button_cancel",
            content: "Close",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal))",
            content: "Closed",
        },
    ],
});

// 3.1, 3.2: grouped by call, with the score and the position.
registry.category("web_tour.tours").add("ems_erasmus_list_applications", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_application",
    steps: () => [
        {
            trigger: `.o_list_view .o_group_header:contains('${CALL}')`,
            content: "Grouped by call",
        },
        {
            trigger: ".o_list_view th[data-name='score_total']",
            content: "The score is a column",
        },
        {
            trigger: ".o_list_view th[data-name='rank']",
            content: "So is the position",
        },
        {
            trigger: ".o_list_view:not(:has(th[data-name='call_id']))",
            content: "The call does not repeat in every row",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='rank']:empty",
            content: "No position yet: nothing, not a 0",
        },
    ],
});

// 7.2: from the menu, what every call has.
registry.category("web_tour.tours").add("ems_erasmus_list_ranking_menu", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_ranking",
    steps: () => [
        {
            trigger: `.o_list_view .o_group_header:contains('${CALL}')`,
            content: "Grouped by call",
        },
        {
            trigger: ".o_list_view th[data-name='score_total']",
            content: "The total is there",
        },
        {
            trigger: ".o_list_view:not(:has(th[data-name='score_a'])):not(:has(th[data-name='score_plan']))",
            content: "No criteria of one kind of call",
        },
        {
            trigger: ".o_list_view .o_data_row:not(.text-success):not(.text-danger):not(.text-warning)",
            content: "No row colour",
        },
    ],
});

// 4.1: from the call, grouped by modality, with its criteria, and the name in full.
registry.category("web_tour.tours").add("ems_erasmus_list_ranking_call", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view button[name='action_view_ranking']",
            content: "Open the call's ranking",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_group_header:contains('TGM')",
            content: "Grouped by modality",
        },
        {
            trigger: ".o_list_view th[data-name='score_a']",
            content: "With its criteria",
        },
        {
            trigger: ".o_list_view:not(:has(th[data-name='is_eligible'])):not(:has(th[data-name='score_complete']))",
            content: "The ticks are hidden",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='partner_id']:contains('Erasmus Test Student')",
            content: "The name",
            run() {
                if (this.anchor.scrollWidth > this.anchor.clientWidth) {
                    throw new Error("The name is cut");
                }
            },
        },
    ],
});

// 4.10: withdrawing an offer is inside the table.
registry.category("web_tour.tours").add("ems_erasmus_list_offers", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_offer",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row button[name='action_cancel']",
            content: "The button is in the page",
            run() {
                const right = this.anchor.getBoundingClientRect().right;
                if (right > window.innerWidth) {
                    throw new Error(`The button ends at ${right}, the page at ${window.innerWidth}`);
                }
            },
        },
        {
            trigger: ".o_list_view .o_data_row:not(.text-success):not(.text-danger):not(.text-muted)",
            content: "No row colour",
        },
    ],
});

// 4.7: the group mobility column only when asked for.
registry.category("web_tour.tours").add("ems_erasmus_list_resolutions", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_resolution",
    steps: () => [
        {
            trigger: ".o_list_view th[data-name='kind']",
            content: "The list",
        },
        {
            trigger: ".o_list_view:not(:has(th[data-name='group_mobility_id']))",
            content: "Hidden by default",
        },
    ],
});

// 7.6, 7.7: one row per applicant, with the mean and how many rated, and no pivot.
registry.category("web_tour.tours").add("ems_erasmus_list_plan_ratings", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_plan_rating",
    steps: () => [
        {
            trigger: ".o_list_view .o_group_header:contains('Erasmus Staff 1')",
            content: "Grouped by applicant",
        },
        {
            trigger: ".o_list_view .o_group_header:contains('Erasmus Staff 1') td:contains('1')",
            content: "How many rated, in the group's row",
        },
        {
            trigger: ".o_control_panel:not(:has(.o_switch_view.o_pivot))",
            content: "No pivot",
        },
    ],
});
