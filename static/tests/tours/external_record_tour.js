/** @odoo-module **/

import { registry } from "@web/core/registry";
import { clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";
import { uploadCertificate } from "@ems/../tests/tours/external_record_helpers";

// A previous record (issue #585) - a course taken at another centre, or at this one before EMS - added to the academic history, driven as the
// secretariat - who processes academic file transfers and is the least-privileged role allowed.
//
// Covers every rendering the feature adds or reuses: the entry in the student form's Actions
// dropdown, the wizard that opens the record, the grade review dialog it hands over to (with its
// "previous record" notice and its "Apply and add another module" button, which reopens it), and
// the new record landing in the Academic history tab of the student form.

function pickModule(name) {
    return [
        {
            trigger: ".modal div[name='subject_id'] input",
            content: `Pick the module ${name}`,
            run: `edit ${name}`,
        },
        {
            trigger: `.o-autocomplete--dropdown-item:contains('${name}')`,
            content: "Select it",
            run: "click",
        },
    ];
}

function typeGrade(row, score) {
    return [
        {
            trigger: `.modal div[name='line_ids'] .o_data_row:nth-child(${row}) [name='score']`,
            content: `Open the grade of learning outcome ${row}`,
            run: "click",
        },
        {
            trigger: `.modal div[name='line_ids'] .o_data_row:nth-child(${row}) [name='score'] input`,
            content: `Type the certificate's grade ${score}`,
            run: `edit ${score}`,
        },
    ];
}

registry.category("web_tour.tours").add("ems_external_record", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .o_field_widget[name='name']:contains('External Record Tour Student'), .o_form_view .o_field_widget[name='name'] input",
            content: "The student form is loaded",
        },
        ...clickAction("action_external_record_wizard", "Add a previous record"),
        {
            trigger: ".modal div[name='course_id'] input",
            content: "Pick the course taken elsewhere",
            run: "edit 2078",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('2078-2079')",
            content: "Select it",
            run: "click",
        },
        {
            trigger: ".modal div[name='study_id'] input",
            content: "Pick the study",
            run: "edit External Record Tour Study",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('External Record Tour Study')",
            content: "Select it",
            run: "click",
        },
        {
            trigger: ".modal div[name='origin_centre_name'] input",
            content: "Type the origin centre",
            run: "edit Institut Extern Tour",
        },
        {
            trigger: ".modal footer button[name='action_create']",
            content: "Create the record and go on to its modules",
            run: "click",
        },
        {
            trigger: ".modal .alert-info:not(.d-none):contains('typed in from an academic certificate')",
            content: "The grade review opened with the previous-record notice",
        },
        ...pickModule("External Record Tour Subject B"),
        {
            trigger: ".modal div[name='line_ids'] .o_data_row:nth-child(1)",
            content: "The learning outcome grid was filled from the teaching plan",
        },
        ...typeGrade(1, 8),
        {
            trigger: ".modal footer button[name='action_apply_and_add']",
            content: "Apply and add another module",
            run: "click",
        },
        {
            trigger: ".modal div[name='line_ids']:not(:has(.o_data_row))",
            content: "The dialog reopened, empty, for the next module",
        },
        ...pickModule("External Record Tour Subject A"),
        {
            trigger: ".modal div[name='line_ids'] .o_data_row:nth-child(2)",
            content: "Both learning outcomes of the module are listed",
        },
        ...typeGrade(1, 7),
        ...typeGrade(2, 6),
        {
            trigger: ".modal footer button[name='action_apply']",
            content: "Apply the last module",
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
            trigger: ".o_form_view div[name='year_record_ids'] .o_data_row:contains('2078-2079')",
            content: "The record shows in the student's Academic history",
        },
    ],
});

// The same, from an Esfera academic record PDF (an invented one the test serves through an
// xmlid): upload it, check and correct the review grid, and create the record in one go.
registry.category("web_tour.tours").add("ems_external_record_certificate", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .o_field_widget[name='name']:contains('External Record Tour Student'), .o_form_view .o_field_widget[name='name'] input",
            content: "The student form is loaded",
        },
        ...clickAction("action_external_record_wizard", "Add a previous record"),
        uploadCertificate("ems.tour_external_record_certificate"),
        {
            trigger: ".modal div[name='origin_centre_name'] input:value(Institut Inventat Tour)",
            content: "The origin centre was read from the certificate",
        },
        {
            trigger: ".modal div[name='line_ids'] .o_data_row:contains('M_OP_09') td[name='warning']:not(:empty)",
            content: "The other centre's optional module is flagged as not imported",
        },
        {
            trigger: ".modal div[name='line_ids'] .o_data_row:contains('EXRTSUBA_EXRT_02RA') td[name='score']",
            content: "Open the grade of outcome two",
            run: "click",
        },
        {
            trigger: ".modal div[name='line_ids'] .o_data_row:contains('EXRTSUBA_EXRT_02RA') td[name='score'] input",
            content: "Correct it",
            run: "edit 9",
        },
        {
            trigger: ".modal footer button[name='action_create']",
            content: "Create the record with every module",
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
            trigger: ".o_form_view div[name='year_record_ids'] .o_data_row:contains('2078-2079')",
            content: "The record shows in the student's Academic history",
        },
    ],
});
