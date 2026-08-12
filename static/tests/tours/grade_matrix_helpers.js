/** @odoo-module **/

// Shared by every tour driving one of the bespoke "grade matrix" grids
// (widget="grade_matrix" on ems.grade_session's form, and the ems.grade_tutor_matrix client
// action) - both render cells as plain <td>s (not standard field widgets), edited via a
// dblclick that renders a floating <input class="o_grade_matrix_input"> only while that one
// cell is active (removed again on blur). The tour engine's generic "click"/"edit" actions have
// no concept of this - the whole interaction (dblclick, wait for the input to render, focus it,
// type, blur to commit into the widget's own buffer) has to be driven by hand.
export function editGradeMatrixCell(selector, value) {
    return {
        trigger: selector,
        content: `Double-click a grade matrix cell and enter ${value}`,
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
