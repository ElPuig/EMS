/** @odoo-module **/

// The Students list shows the first name and the last names as columns of their own, never the
// complete name (issue #655). partner_firstname, with the centre's "first_last" order, keeps the
// first word of a name as the first name and the rest as the last names. `name` is (part of) a
// complete name: whether or not it starts with the first name, everything after its first word is
// in the last names, so the row is found by that.
export function studentRow(name) {
    const lastnames = name.split(" ").slice(1).join(" ") || name;
    return `.o_data_row:has(.o_data_cell[name='lastname']:contains('${lastnames}'))`;
}

// A cell of that student's row, to open it.
export function studentCell(name) {
    return `${studentRow(name)} .o_data_cell[name='lastname']`;
}

// Steps searching the Students list for `text`, so a test student is found on the first page
// whatever the centre's own students are: the list is sorted by last name.
export function searchStudent(text) {
    return [
        // Only once the list is loaded: typed while the view is still switching, the text is lost.
        { trigger: ".o_list_view .o_data_row", content: "The list is loaded" },
        { trigger: ".o_searchview_input", content: `Search for ${text}`, run: `edit ${text}` },
        { trigger: ".o_searchview_input", content: "Confirm the search", run: "press Enter" },
        { trigger: `.o_searchview_facet:contains('${text}')`, content: "The search facet is applied" },
    ];
}
