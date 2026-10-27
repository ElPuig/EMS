/** @odoo-module **/

import { registry } from "@web/core/registry";
import { clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";
import { uploadCertificate } from "@ems/../tests/tours/external_record_helpers";

// A previous curriculum record (issue #672) imported from its academic history document (an
// invented one the test serves through an xmlid), driven as the secretariat - the least-privileged
// role allowed. Covers every rendering the feature adds: the entry in the student form's Actions
// dropdown, the wizard and its review grid, the record in the student's Studies tab, and the
// standalone list and form of the records.
registry.category("web_tour.tours").add("ems_previous_curriculum_record", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .o_field_widget[name='name']:contains('Previous Curriculum Tour Student'), .o_form_view .o_field_widget[name='name'] input",
            content: "The student form is loaded",
        },
        ...clickAction("action_previous_curriculum_wizard", "Import a previous curriculum record"),
        uploadCertificate("ems.tour_previous_curriculum_document"),
        {
            trigger: ".modal div[name='curriculum_name'] input:value(CFPS Cicle Tour (LOE))",
            content: "The curriculum was read from the document",
        },
        {
            trigger: ".modal div[name='line_ids'] .o_data_row:contains('00201') td[name='grade']",
            content: "Open the grade of the pending unit",
            run: "click",
        },
        {
            trigger: ".modal div[name='line_ids'] .o_data_row:contains('00201') td[name='grade'] input",
            content: "Correct it",
            run: "edit 6",
        },
        {
            trigger: ".modal footer button[name='action_create']",
            content: "Create the record",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal))",
            content: "The dialog is closed",
        },
        {
            trigger: ".o_form_view .o_notebook a[name='studies']",
            content: "Open the Studies tab",
            run: "click",
        },
        {
            trigger: ".o_form_view div[name='previous_curriculum_record_ids'] .o_data_row:contains('CFPS Cicle Tour (LOE)')",
            content: "The record shows in the student's history",
        },
        {
            trigger: ".o_main_navbar",
            content: "Open the list of previous curriculum records",
            run() {
                window.location.href = "/odoo/action-ems.action_previous_curriculum_record_list";
            },
        },
        {
            trigger: ".o_list_view .o_data_row:contains('Previous Curriculum Tour Student') td[name='student_id']",
            content: "Open the record",
            run: "click",
        },
        {
            trigger: ".o_form_view div[name='line_ids'] .o_data_row:contains('UF1. Unitat pendent') td[name='grade']:contains('6')",
            content: "The record holds its units with the corrected grade",
        },
    ],
});
