/** @odoo-module **/

import { registry } from "@web/core/registry";

// widget="grade_matrix" (grade_outcome_line_ids on ems.grade_session's form) is a bespoke
// spreadsheet-like grid: cells are plain <td>s, not standard field widgets, edited via a
// dblclick that renders a floating <input> only while that one cell is active (removed again
// on blur). The tour engine's generic "click"/"edit" actions have no concept of this - the
// whole interaction (dblclick, wait for the input to render, focus it, type, blur to commit
// into the widget's own buffer via its t-on-blur="commitEdit") is driven by hand in one step,
// the same spirit as the Ace-editor custom run() already established for widget="code" (see
// limesurvey_block_tour.js).
function editGradeCell(value) {
    return {
        trigger: ".o_grade_matrix tbody tr:first-child td.o_grade_matrix_cell",
        content: `Double-click the first outcome cell and enter ${value}`,
        run: async (helpers) => {
            helpers.anchor.dispatchEvent(new MouseEvent("dblclick", { bubbles: true }));
            // OWL patches the DOM asynchronously after the dblclick handler flips edit.active -
            // one requestAnimationFrame isn't reliably enough, poll for a bit instead of
            // assuming a fixed number of frames covers it.
            let input = null;
            for (let i = 0; i < 50 && !input; i++) {
                input = helpers.anchor.querySelector("input.o_grade_matrix_input");
                if (!input) {
                    await new Promise((resolve) => setTimeout(resolve, 20));
                }
            }
            if (!input) {
                throw new Error("The grade matrix's floating edit input never appeared after the dblclick.");
            }
            input.focus();
            input.value = value;
            input.dispatchEvent(new Event("input", { bubbles: true }));
            input.blur();
        },
    };
}

// ems.grade_session's form is create="0"/duplicate="0" (sessions are only created through the
// grade_session_wizard, already covered by grade_session_tour.js) - this tour opens a
// pre-seeded session from the list instead, matching the "existing record from a list" pattern
// already used by strike_tour.js's ems_strike_consult.
registry.category("web_tour.tours").add("ems_grade_matrix_entry", {
    test: true,
    url: "/odoo/action-ems.action_grade_session_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Grade sessions list loaded",
        },
        // The action's own context defaults to grouping by round then group (see menu.xml),
        // so the seeded session starts hidden inside a collapsed group row, not a flat
        // .o_data_row - expand it by its computed group name ('TGMX1A': study acronym 'TGMX' +
        // course '1' + group acronym 'A', see ems.group's _compute_name) before it can be
        // clicked.
        {
            trigger: ".o_list_view .o_group_header:contains('TGMX1A')",
            content: "Expand the seeded session's group",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='subject_id']:contains('Test Subject (Grade Matrix Tour)')",
            content: "Open the seeded grade session",
            run: "click",
        },
        {
            trigger: ".o_grade_matrix table tbody tr",
            content: "Grade matrix grid rendered with student rows",
        },
        editGradeCell("8"),
        {
            trigger: ".o_grade_matrix_toolbar button:not(:disabled)",
            content: "Apply changes is enabled now that the buffer is dirty",
            run: "click",
        },
        {
            trigger: ".o_grade_matrix tbody tr:first-child td.o_grade_matrix_cell span:contains('8')",
            content: "The entered score persisted and re-rendered after apply",
        },
    ],
});
