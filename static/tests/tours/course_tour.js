/** @odoo-module **/

import { registry } from "@web/core/registry";

// ems.course has no menu/list/form of its own — the only real UI surface is the "Current
// course" selector on the Settings page (res.config.settings → current_course_id on
// res.company). This tour is the only browser coverage this model gets; it also covers the
// company._sync_current_course_flag() integration indirectly (selecting a course here is
// exactly what flips ems.course.is_current).
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
            trigger: ".o_form_button_save, .settings .o_form_button_save",
            content: "Save the setting",
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
