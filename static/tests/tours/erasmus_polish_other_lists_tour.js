/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #782 - the lists of mobilities, groups, projects, economy and configuration. Records seeded
// by tests/test_erasmus_polish_other_lists_tour.py.

const STUDENT = "Erasmus Test Student";
const GROUP = "Test SMX2 morning";

function openTab(name) {
    return {
        trigger: `.o_notebook a.nav-link[name='${name}']`,
        content: `The ${name} tab`,
        run: "click",
    };
}

function switchView(type) {
    return {
        trigger: `.o_control_panel .o_switch_view.o_${type}`,
        content: `Switch to the ${type} view`,
        run: "click",
    };
}

// 5.1, 5.2, 5.8, 8.7, 8.12: the list, the cards by phase and the record's table.
registry.category("web_tour.tours").add("ems_erasmus_other_lists_mobilities", {
    test: true,
    steps: () => [
        {
            trigger: `.o_list_view .o_data_row:contains('${STUDENT}') td[name='record_progress']`,
            content: "Each mobility says how its record is going",
        },
        {
            trigger: ".o_list_view:not(:has(th[data-name='proposal_state']))",
            content: "The proposal only when asked for",
        },
        switchView("kanban"),
        {
            trigger: ".o_kanban_view .o_kanban_group .o_kanban_header",
            content: "One column per phase",
        },
        {
            trigger: `.o_kanban_view .o_kanban_record:contains('${STUDENT}') .fa-folder-open-o`,
            content: "The card with the record's progress",
        },
        {
            trigger: `.o_kanban_view .o_kanban_record:contains('${STUDENT}')`,
            content: "Open the mobility",
            run: "click",
        },
        openTab("documents"),
        {
            trigger: ".o_field_widget[name='document_ids'] th[data-name='responsible']",
            content: "Who handles each document",
        },
        {
            trigger: ".o_field_widget[name='document_ids'] th[data-name='todo_state']",
            content: "And, apart, what it is at",
        },
        {
            trigger: ".o_field_widget[name='document_ids'] table:not(:has(th[data-name='attachment_ids']))",
            content: "Every version only when asked for",
        },
        {
            // The fixture attaches a file to a document the team hands over and to one the
            // participant provides: only the first may show it.
            trigger: ".o_field_widget[name='document_ids'] td[name='prepared_attachment_ids']:contains('team-file.pdf')",
            content: "The team's files only on a document the team hands over",
            run() {
                const shown = document.querySelectorAll(
                    ".o_field_widget[name='document_ids'] td[name='prepared_attachment_ids']"
                );
                const withFile = [...shown].filter((cell) => cell.textContent.includes("team-file.pdf"));
                if (withFile.length !== 1) {
                    throw new Error(`The team's file shows on ${withFile.length} documents, expected 1`);
                }
            },
        },
    ],
});

// 5.18: what was proposed, to decide on it.
registry.category("web_tour.tours").add("ems_erasmus_other_lists_to_validate", {
    test: true,
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='proposal_host']:contains('Tour Proposed Host')",
            content: "The proposed entity",
        },
        {
            trigger: ".o_list_view:not(:has(th[data-name='destination_id']))",
            content: "Not the columns that stay empty until it is validated",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='partner_id']",
            content: "Open it",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook a.nav-link[name='proposal']",
            content: "The mobility's form, with its proposal",
        },
    ],
});

// 10.9, 10.11, 10.12: the projects.
registry.category("web_tour.tours").add("ems_erasmus_other_lists_projects", {
    test: true,
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='name']:contains('TOUR-OTHER-LISTS')",
            content: "The project",
        },
        {
            trigger: ".o_list_view:not(:has(.o_boolean_toggle)):not(:has(th[data-name='keep_until']))",
            content: "No switch that archives it; the keeping date only when asked for",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='name']:contains('TOUR-OTHER-LISTS')",
            content: "Open it",
            run: "click",
        },
        openTab("mobilities"),
        {
            trigger: `.o_field_widget[name='mobility_ids'] .o_data_row:contains('${STUDENT}')`,
            content: "Its individual mobilities, under their title",
        },
        {
            trigger: ".o_notebook .tab-pane.active:not(:has(.o_field_widget[name='group_mobility_ids']))",
            content: "No group mobilities table when there are none",
        },
        openTab("exports"),
        {
            trigger: `.o_field_widget[name='export_ids'] .o_data_row td[name='subject']:contains('${STUDENT}')`,
            content: "What was exported, with the participant's name",
        },
        {
            trigger: ".o_field_widget[name='export_ids'] table:not(:has(th[data-name='scope']))",
            content: "Five columns",
        },
    ],
});

// 11.4, 11.5, 11.6: the economy.
registry.category("web_tour.tours").add("ems_erasmus_other_lists_panel", {
    test: true,
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='name']:contains('TOUR-OTHER-LISTS')",
            content: "The economic panel",
        },
        switchView("pivot"),
        {
            trigger: ".o_pivot table thead",
            content: "The comparison by call opens with three figures",
            run() {
                const measures = document.querySelectorAll(".o_pivot thead .o_pivot_measure_row");
                // Three per kind of project plus the total's three.
                if (measures.length % 3 !== 0 || measures.length > 9) {
                    throw new Error(`Unexpected number of measures: ${measures.length}`);
                }
            },
        },
    ],
});

registry.category("web_tour.tours").add("ems_erasmus_other_lists_expenses", {
    test: true,
    steps: () => [
        {
            trigger: ".o_list_view th[data-name='counted_amount']",
            content: "One amount, the one that counts",
        },
        {
            trigger: ".o_list_view:not(:has(th[data-name='amount'])):not(:has(th[data-name='supplier_id']))",
            content: "Not the amount typed in, nor the empty columns",
        },
    ],
});

registry.category("web_tour.tours").add("ems_erasmus_other_lists_payments", {
    test: true,
    steps: () => [
        {
            trigger: ".o_list_view th[data-name='kind']",
            content: "The grant payments",
        },
        {
            trigger: ".o_list_view:not(:has(th[data-name='group_mobility_id']))",
            content: "The group mobility only when asked for",
        },
    ],
});

// 13.4, 13.8, 12.9: configuration and quality.
registry.category("web_tour.tours").add("ems_erasmus_other_lists_config", {
    test: true,
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row:contains('Tour Host Entity') td[name='erasmus_mobility_count']:contains('1')",
            content: "The host entity, with how many mobilities it has hosted",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('Tour Host Entity') td[name='erasmus_oid']:contains('E10TOUR1')",
            content: "And its OID",
        },
        {
            trigger: ".o_action:not(:has(.o_search_panel))",
            content: "No side panel of student groups",
        },
        switchView("kanban"),
        {
            trigger: ".o_kanban_view .o_kanban_record:contains('Tour Host Entity')",
            content: "The cards",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='erasmus_oid']",
            content: "The entity's form",
        },
    ],
});

registry.category("web_tour.tours").add("ems_erasmus_other_lists_rates", {
    test: true,
    steps: () => [
        {
            trigger: ".o_list_view .o_group_header:contains('2026')",
            content: "The rates, grouped by year",
        },
        {
            trigger: ".o_list_view:not(:has(.o_group_header:contains('2.026')))",
            content: "The year without a thousands separator",
        },
    ],
});

registry.category("web_tour.tours").add("ems_erasmus_other_lists_surveys", {
    test: true,
    steps: () => [
        {
            trigger: ".o_action_manager .o_list_view",
            content: "The surveys",
        },
        {
            trigger: ".o_control_panel:not(:has(.o_switch_view.o_pivot))",
            content: "No pivot: the quality panel breaks the satisfaction down",
        },
    ],
});

// 9.8, 9.10: the group mobility, as its leader.
registry.category("web_tour.tours").add("ems_erasmus_other_lists_group", {
    test: true,
    steps: () => [
        {
            trigger: `.o_kanban_view .o_kanban_record:contains('${GROUP}')`,
            content: "Open the group mobility",
            run: "click",
        },
        openTab("selection"),
        {
            trigger: ".o_field_widget[name='registration_ids'] th[data-name='ranking_average']",
            content: "The students with their average and result",
        },
        {
            trigger: ".o_field_widget[name='registration_ids'] table:not(:has(th[data-name='strike_count'])):not(:has(th[data-name='eligible']))",
            content: "The rest of the columns only when asked for",
        },
        openTab("participants"),
        {
            trigger: ".o_field_widget[name='participant_ids'] th[data-name='documents_missing']",
            content: "The participants",
        },
        {
            trigger: ".o_field_widget[name='participant_ids'] table:not(:has(th[data-name='email'])):not(:has(th[data-name='commitment_pending']))",
            content: "Seven columns",
        },
    ],
});
