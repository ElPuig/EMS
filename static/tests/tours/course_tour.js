/** @odoo-module **/

import { registry } from "@web/core/registry";

// Browser coverage for the two UI surfaces of ems.course, both on the Settings page:
// the "Current course" selector (res.config.settings → current_course_id on res.company,
// which is what flips is_current through _sync_current_course_flag) and the "Manage
// courses" dialog, the only way to move is_enrollment_default without a data file or a
// shell.
registry.category("web_tour.tours").add("ems_course_settings", {
    test: true,
    url: "/odoo/action-ems.action_settings",
    steps: () => [
        {
            trigger: ".o_field_widget[name='current_course_id'] input",
            content: "Settings page loaded with the Current course selector",
        },
        {
            trigger: ".o_field_widget[name='current_course_id'] input",
            content: "Search for the tour's own course",
            run: "edit 2099-2100",
        },
        {
            trigger: ".o-autocomplete--dropdown-menu li:contains('2099-2100')",
            content: "Select the 2099-2100 course from the dropdown",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='current_course_id'] input",
            content: "Confirm the field shows the selected course (checking .value directly — "
                + "OWL doesn't sync the value HTML attribute, so a CSS [value=...]/:contains "
                + "selector on the input itself would not work here)",
            run: () => {
                const input = document.querySelector(".o_field_widget[name='current_course_id'] input");
                if (!input.value.includes("2099-2100")) {
                    throw new Error(`current_course_id shows "${input.value}", expected 2099-2100`);
                }
            },
        },
        {
            // The twin selector: same mechanism, for the mark that says which course new
            // enrollments are created for. Moving it here is a single action even though
            // the flag is unipersonal, because _sync_enrollment_course_flag clears the
            // previous one before setting this one.
            trigger: ".o_field_widget[name='enrollment_course_id'] input",
            content: "Search the same course in the Enrollment course selector",
            run: "edit 2099-2100",
        },
        {
            trigger: ".o-autocomplete--dropdown-menu li:contains('2099-2100')",
            content: "Select it",
            run: "click",
        },
        {
            trigger: ".o_form_button_save, .settings .o_form_button_save",
            content: "Save the settings",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='current_course_id'] input",
            content: "Setting saved — confirm the value still reads back correctly after save",
            run: () => {
                const input = document.querySelector(".o_field_widget[name='current_course_id'] input");
                if (!input.value.includes("2099-2100")) {
                    throw new Error(`current_course_id shows "${input.value}" after save, expected 2099-2100`);
                }
            },
        },
    ],
});
