/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #416: the Department Chief field (hr.department.manager_id) used to be required at the
// view level (views/community/department/form.xml) for every non-top-level, non-sharing
// department, blocking an admin from ever saving a department with no Chief - which can
// legitimately happen mid course-transition (the outgoing Chief removed before a new one is
// assigned). The model itself already tolerates an empty manager_id
// (hr.department._effective_manager() returns an empty recordset "left for an admin to
// configure"); only the form ever blocked it. This tour proves the form allows it too.
registry.category("web_tour.tours").add("ems_department_head_optional", {
    test: true,
    url: "/odoo/action-ems.action_department_tree",
    steps: () => [
        {
            // "Hide main departments" (views/community/department/search.xml) is active by
            // default and hides every department with no parent_id - not only is_top_level ones.
            // The tour's own fixture has no parent either, so it stays hidden until this filter
            // is removed.
            trigger: ".o_searchview_facet:contains('Hide main departments') .o_facet_remove",
            content: "Remove the default 'Hide main departments' filter so the fixture (parent-less) shows up",
            run: "click",
        },
        {
            // The EMS-specific department search view has no default text-search field at all
            // (only that filter and a parent_id search panel) - so, unlike most other list views
            // in this project, a typed search here falls through to "Add Custom Filter" instead
            // of a name facet. Matching the fixture's own row by its own name text is the safe
            // way to find it instead (this is text the tour itself created, not translatable UI
            // vocabulary).
            trigger: ".o_list_view .o_data_row td[name='name']:contains('Department Head Optional Tour Department')",
            content: "Open the fixture department",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='manager_id'] input",
            content: "Department Chief starts assigned",
        },
        {
            trigger: ".o_field_widget[name='manager_id'] input",
            content: "Clear the Department Chief",
            run: "clear",
        },
        {
            // Many2XAutocomplete only actually commits an empty selection (calling
            // props.update(false)) from its own "change" event, fired on blur - typing/clearing
            // alone (and Escape, which merely closes the now-empty dropdown without resetting
            // anything) leaves the field's real value untouched until focus moves elsewhere.
            trigger: ".o_form_view .o_field_widget[name='name'] input",
            content: "Blur the Department Chief field so the cleared value actually commits",
            run: "click",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save with no Department Chief",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_saved",
            content: "The department saved with no Department Chief - the field is no longer required",
        },
        {
            // Verify in the list view after save (per project convention), not via the form's
            // own widget state - the many2one autocomplete can re-render/re-open its dropdown
            // right after a save, which would make an in-form assertion flaky for reasons
            // unrelated to what this tour is actually proving.
            trigger: ".o_breadcrumb a",
            content: "Back to the list",
            run: "click",
        },
        {
            trigger:
                ".o_list_view .o_data_row:has(td[name='name']:contains('Department Head Optional Tour Department')) td[name='effective_manager_id']:empty",
            content: "The Department Chief really persisted empty - checked in the list, not via the form widget",
        },
    ],
});
