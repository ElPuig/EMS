/** @odoo-module **/

import { registry } from "@web/core/registry";

// Smoke-tests the free-pick color widget on ems.role's own screens (list + form) — this is
// what broke silently before: a clean ./upgrade.sh and passing TransactionCase tests never
// render a view in a real browser, so a client-side (OWL template/widget) crash here would
// have gone unnoticed the same way it did for the department kanban. See
// docs/en/developers/shared/color_widget.md.
registry.category("web_tour.tours").add("ems_role_color_smoke", {
    test: true,
    url: "/odoo/action-ems.action_teachers_role_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Roles list view loaded",
        },
        {
            trigger: ".o_list_view .o_data_row:first-child .o_field_color",
            content: "Color swatch rendered in the list",
        },
        {
            trigger: ".o_list_view .o_data_row:first-child td[name='name']",
            content: "Open the first role",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='color'] .o_field_color",
            content: "Color swatch rendered on the form",
        },
    ],
});

// Smoke-tests role_color_tags: ems.role data embedded in a DIFFERENT model's view
// (hr.employee's kanban card and form, via role_ids) — the specific gap the previous
// per-model-only tour convention missed.
registry.category("web_tour.tours").add("ems_employee_role_badge_smoke", {
    test: true,
    url: "/odoo/action-ems.action_employee_kanban",
    steps: () => [
        {
            trigger: ".o_kanban_view",
            content: "Teachers kanban view loaded",
        },
        {
            trigger: ".o_kanban_record:first-child",
            content: "Open the first teacher",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='role_ids'] input",
            // Coexistence coordinator is not unipersonal, so this works regardless of who
            // else already holds it - unlike most of the catalog's other manually-assignable
            // roles, which are unipersonal and may already be taken by another teacher.
            content: "Search for the Coexistence coordinator role",
            run: "edit Coexistence coordinator",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Coexistence coordinator')",
            content: "Select it from the dropdown",
            run: "click",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            // Wait for the save round-trip to actually settle before checking the badge -
            // otherwise the check below can pass on an optimistic client-side render while the
            // save request is still in flight, leaving the form "in edition mode" when the test
            // harness closes the page (a full-suite-only failure: harmless in isolation, but
            // flagged when many other tests run first). ".o_form_button_save" always exists in
            // the DOM (form_status_indicator.xml) - only its wrapper's "invisible" class toggles
            // with dirty state, so ":not(:visible)" (not ":not(:has(...))") is what actually
            // detects "no longer dirty" here.
            trigger: ".o_form_button_save:not(:visible)",
            content: "Wait for the save to fully complete",
        },
        {
            trigger:
                ".o_field_widget[name='role_ids'] .o_tag:contains('Coexistence coordinator')[style*='background-color']",
            content: "Role badge rendered with its own background color (not the default o_tag_color class)",
        },
    ],
});

// Smoke-tests the "Assigned to" tab lock for the 7 hierarchy-managed roles
// (views/community/role/form.xml, views/community/employee/kanban.xml): a role-specific
// explanation banner, and the kanban card's own custom delete button (this project's own
// addition, views/community/employee/kanban.xml - not a native Odoo affordance) hidden via
// "read_only_mode", the standard kanban card template variable that already reflects the
// embedding field's own readonly - see that file's own comment for the framework source
// reference. A clean ./upgrade.sh only proves the view's XML is structurally valid, not that
// the banner text/hidden button actually render in a real browser - this is exactly the kind
// of client-side gap that already broke silently once this same session, when a first attempt
// (a dynamic 'class' expression) crashed the whole form's OWL template compilation.
registry.category("web_tour.tours").add("ems_role_hierarchy_lock_smoke", {
    test: true,
    url: "/odoo/action-ems.action_teachers_role_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Roles list view loaded",
        },
        {
            trigger: ".o_data_row td:contains('Head of studies')",
            content: "Open the Head of Studies role",
            run: "click",
        },
        {
            trigger: ".o_form_view .alert-info:contains('Area Manager')",
            content: "Role-specific explanation banner rendered (naming the actual screen to use)",
        },
        {
            trigger:
                ".o_field_widget[name='employee_ids'] .o_kanban_record:not(:has(.o_widget_hr_employee_delete))",
            content: "No delete button rendered on the assigned employee's card",
        },
        {
            trigger: ".breadcrumb-item:contains('Roles')",
            content: "Back to the roles list",
            run: "click",
        },
        {
            trigger: ".o_data_row td:contains('Quality coordinator')",
            content: "Open a minor (non-hierarchy-managed) role for contrast",
            run: "click",
        },
        {
            trigger: ".o_form_view:not(:has(.alert-info))",
            content: "No lock banner for a minor role",
        },
        {
            trigger:
                ".o_field_widget[name='employee_ids'] .o_kanban_record:has(.o_widget_hr_employee_delete)",
            content: "Delete button still rendered for a minor role's assigned employee",
        },
    ],
});
