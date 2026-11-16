/** @odoo-module **/

import { registry } from "@web/core/registry";
import { clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

const ROW = ".o_list_view .o_data_row:contains('WLT')";

// Issue #800 (test_student_walkout_tour.py): two calls of the same group, on different walkout days.
// The group's tutor aborts the one being voted, with a reason, after reading which reasons are
// lawful; the Head of Studies validates the closed one, which justifies the students who join.
registry.category("web_tour.tours").add("ems_student_walkout_abort", {
    test: true,
    url: "/odoo/action-ems.action_student_walkout",
    steps: () => [
        {
            trigger: `${ROW} .o_field_badge:contains('Voting')`,
            content: "Open the call being voted",
            run: "click",
        },
        {
            trigger: ".o_form_view .alert-info:contains('tutor watches over the proposal')",
            content: "The form says the tutor watches over the proposal",
        },
        ...clickAction("action_open_reject_wizard", "Abort it"),
        {
            trigger: ".modal .alert-warning:contains('LODE')",
            content: "The wizard explains which reasons are lawful",
        },
        {
            trigger: ".modal .o_field_widget[name='reason_id'] input",
            content: "Pick a reason",
            run: "edit Other reasons",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Other reasons')",
            content: "Other reasons",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='details'] textarea",
            content: "Other reasons need details",
            run: "edit A dockers' strike",
        },
        {
            trigger: ".modal button[name='action_reject']:visible",
            content: "Abort the proposal",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='rejection_details']:contains('dockers')",
            content: "The proposal is aborted, with its reason",
        },
        {
            trigger: ".o_breadcrumb .breadcrumb-item:first-child a",
            content: "Back to the list",
            run: "click",
        },
        {
            trigger: `${ROW} .o_field_badge:contains('Closed')`,
            content: "The closed call is listed too",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='group_yes_count']:contains('2')",
            content: "The form shows the anonymous group vote, with nothing left for the tutor to do",
        },
    ],
});

registry.category("web_tour.tours").add("ems_student_walkout_validate", {
    test: true,
    url: "/odoo/action-ems.action_student_walkout",
    steps: () => [
        {
            trigger: `${ROW} .o_field_badge:contains('Closed')`,
            content: "Open the closed call, waiting to be validated",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='line_ids'] .o_data_row:contains('WLT Delegate')",
            content: "The form shows every student of the group",
        },
        ...clickAction("action_generate_justification", "Validate and justify"),
        {
            trigger: ".o_form_view .o_field_widget[name='student_ids']:contains('WLT Delegate')",
            content: "The justification of the walkout day opens, for the students who join",
        },
        {
            trigger: ".o_breadcrumb .breadcrumb-item:first-child a",
            content: "Back to the list",
            run: "click",
        },
        {
            trigger: `${ROW} .o_field_badge:contains('Justified')`,
            content: "The call is validated",
        },
    ],
});

// Settings > Student Walkout Settings > Levels and courses, as a settings administrator who is not
// an academic administrator (test_student_walkout_tour.py): the list is editable and saves.
registry.category("web_tour.tours").add("ems_student_walkout_levels", {
    test: true,
    url: "/odoo/action-ems.action_level_walkout_settings",
    steps: () => [
        {
            trigger: ".modal .o_data_row:contains('WLT') td[name='walkout_course_from']",
            content: "The tour's level, with its first course",
            run: "click",
        },
        {
            trigger: ".modal .o_data_row:contains('WLT') .o_field_widget[name='walkout_course_from'] input",
            content: "From the 2nd course",
            run: "edit 2",
        },
        {
            trigger: ".modal button[name='action_save']",
            content: "Save",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal))",
            content: "The dialog closes",
        },
    ],
});

// Issue #828: Settings > Student Walkout Settings > Calendar, as a settings administrator
// (test_student_walkout_tour.py): the kind of hours hides the other two controls when they do not
// apply, and the example follows every control. Discarded, not saved (see settings_tour.js).
const walkoutBlock = ".app_settings_block[data-key='ems'] #walkout_calendar";
registry.category("web_tour.tours").add("ems_student_walkout_calendar", {
    test: true,
    url: "/odoo/action-base_setup.action_general_configuration",
    steps: () => [
        {
            trigger: ".settings_tab a.tab[data-key='ems']",
            content: "Switch to the EMS Management tab",
            run: "click",
        },
        {
            trigger: `${walkoutBlock} .o_ems_walkout_calendar_example:contains('Each phase starts when its email reaches the group')`,
            content: "The example of today's count: real hours, from the email",
        },
        {
            trigger: `${walkoutBlock} .o_field_widget[name='walkout_count_from'] select`,
            content: "Count from the proposal",
            run: "selectByLabel From the moment of the proposal",
        },
        {
            trigger: `${walkoutBlock} .o_ems_walkout_calendar_example:contains('the emails leave at once')`,
            content: "The example follows",
        },
        {
            trigger: `${walkoutBlock} .o_field_widget[name='walkout_count_days_off'] input`,
            content: "Count the days without class",
            run: "click",
        },
        {
            trigger: `${walkoutBlock} .o_ems_walkout_calendar_example:contains('every day')`,
            content: "The example follows",
        },
        {
            trigger: `${walkoutBlock} .o_field_widget[name='walkout_hours_kind'] select`,
            content: "School hours",
            run: "selectByLabel School hours",
        },
        {
            trigger: `${walkoutBlock}:not(:has(.o_field_widget[name='walkout_count_from'])):not(:has(.o_field_widget[name='walkout_count_days_off'])) .o_ems_walkout_calendar_example:contains('class hours')`,
            content: "The start and the days without class do not apply; the example counts class hours",
        },
        {
            trigger: ".o_form_button_cancel",
            content: "Discard, to leave the form clean",
            run: "click",
        },
        {
            trigger: `${walkoutBlock} .o_field_widget[name='walkout_count_from'] select`,
            content: "Discarded: real hours again",
        },
    ],
});
