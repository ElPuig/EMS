/** @odoo-module **/

import { registry } from "@web/core/registry";

// Smoke-tests the grade import wizard's own screen. The wizard is a TransientModel opened as a
// dialog, so the TransactionCase suite (tests/test_grade_import_wizard.py) exercises the import
// logic but never renders the form: a broken arch or a field missing from the view would only
// show up here. The file upload itself cannot be driven from a tour, so this checks the form
// renders with its inputs — including "Create missing enrollments" — and that the import button
// is there. See docs/en/developers/grades/grade_import_wizard.md.
registry.category("web_tour.tours").add("ems_grade_import_wizard_smoke", {
    test: true,
    url: "/odoo/action-ems.action_grade_import_wizard",
    steps: () => [
        {
            trigger: ".o_dialog .o_form_view",
            content: "Import wizard form rendered",
        },
        {
            trigger: ".o_dialog .o_field_widget[name='round']",
            content: "Evaluation selector rendered",
        },
        {
            trigger: ".o_dialog .o_field_widget[name='file']",
            content: "File input rendered",
        },
        {
            trigger: ".o_dialog .o_field_widget[name='create_missing_enrollments'] input[type='checkbox']",
            content: "The 'Create missing enrollments' checkbox is rendered and unchecked by default",
            run: function () {
                const checkbox = document.querySelector(
                    ".o_dialog .o_field_widget[name='create_missing_enrollments'] input[type='checkbox']"
                );
                if (checkbox.checked) {
                    throw new Error("'Create missing enrollments' must default to unchecked");
                }
            },
        },
        {
            trigger: ".o_dialog .o_field_widget[name='create_missing_enrollments'] input[type='checkbox']",
            content: "Tick it, so the field is proven to be editable and not readonly",
            run: "click",
        },
        {
            trigger:
                ".o_dialog .o_field_widget[name='create_missing_enrollments'] input[type='checkbox']:checked",
            content: "The checkbox holds its new value",
        },
        {
            // Matched by action name, never by label: this database runs in Catalan/Spanish, so a
            // ":contains('Import grades')" trigger would never match.
            trigger: ".o_dialog button[name='action_import']",
            content: "Import button available",
        },
        {
            // Ticking the checkbox above leaves the form dirty, and a tour that ends on a form in
            // edition mode fails ("Form views in edition mode are automatically saved when the page
            // is closed"). Discard by closing the wizard instead of leaving it open.
            trigger: ".modal footer button[special='cancel']",
            content: "Close the wizard without importing",
            run: "click",
        },
        {
            trigger: "body:not(:has(.o_dialog))",
            content: "Wizard closed",
        },
    ],
});
