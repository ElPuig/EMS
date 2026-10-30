/** @odoo-module **/

import { registry } from "@web/core/registry";
import { clickAction } from "./actions_dropdown_helpers";

// Detected absences (issue #509, renamed in issue #696), as the Department Chief who enters them on a teacher of
// their department's behalf (issue #604): the list and the form have to render for that
// role, not only for an officer, and a new entry has to land on the list as pending.
registry.category("web_tour.tours").add("ems_absence_pending", {
    test: true,
    url: "/odoo/action-ems.action_absence_pending",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "The list of detected absences loads",
        },
        {
            trigger: ".o_list_button_add",
            content: "Announce a new one",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='date_from'] input",
            content: "The form opens with the dates prefilled",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='employee_id'] input",
            content: "Search for the teacher, who is in this chief's department",
            run: "edit Tour Pending Teacher",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Tour Pending Teacher')",
            content: "Select them",
            run: "click",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_form_button_save:not(:visible)",
            content: "Saved",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='state'] .o_arrow_button_current[data-value='pending']",
            content: "It stays pending until the teacher requests it",
        },
        {
            trigger: ".o_breadcrumb .o_back_button a, .o_breadcrumb .breadcrumb-item a",
            content: "Back to the list",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('Tour Pending Teacher') td[name='state'] .badge",
            content: "The new entry is listed as pending",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('Tour Pending Teacher') td[name='origin']:not(:empty)",
            content: "With its origin: entered by hand",
        },
    ],
});

// Issue #696: the teacher opens their own detected absence from the reminder's link and
// requests it from there.
registry.category("web_tour.tours").add("ems_absence_pending_teacher", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .o_field_widget[name='origin']",
            content: "The teacher's own detected absence opens, with its origin",
        },
        {
            trigger: ".o_form_view:not(:has(.o_field_widget[name='note']))",
            content: "Without the note of whoever entered it",
        },
        {
            trigger: ".o_form_statusbar .o_field_widget[name='state']:not(:has([data-value='pending']))",
            content: "Without the 'To review' step, a stage the teacher never sees (issue #707)",
        },
        {
            // Issue #735: both ways out, one sentence each.
            trigger: ".o_form_view .alert-info p:nth-of-type(2)",
            content: "A notice tells the teacher what to do",
        },
        ...clickAction("action_request_absence", "Request the absence"),
        {
            trigger: ".o_form_view .o_field_widget[name='request_date_from'] input",
            content: "A new absence request opens, filled in with the day",
        },
        {
            trigger: ".o_breadcrumb .o_back_button a, .o_breadcrumb .breadcrumb-item a",
            content: "Back to the detected absence without requesting it",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='origin']",
            content: "The detected absence is shown again",
        },
        // Issue #735: or the teacher was at the centre. No attendance that day: none is picked.
        ...clickAction("action_request_check_in_correction", "Request check-in correction"),
        {
            trigger: ".modal .o_field_widget[name='absence_pending_id']",
            content: "A correction request about the detected absence opens",
        },
        {
            // The numeric keypad's decimal key writes a comma: minutes, not a fraction of an hour.
            trigger: ".modal .o_field_widget[name='requested_check_in'] input",
            content: "Arrived at 9:15",
            run: "edit 9,15",
        },
        {
            trigger: ".modal .o_field_widget[name='requested_check_out'] input",
            content: "Left at 11:04",
            run: "edit 1104",
        },
        {
            trigger: ".modal .o_field_widget[name='reason'] textarea",
            content: "Why",
            run: "edit I forgot to check in",
        },
        {
            trigger: ".modal .o_field_widget[name='requested_check_in'] input:value('09:15')",
            content: "Read as 09:15",
        },
        {
            trigger: ".modal .o_form_button_save",
            content: "Send the request",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal)) .o_form_view .alert-info:not(:has(p))",
            content: "Back on the detected absence, which now says the correction is being reviewed",
        },
    ],
});

// Issue #707: the Head of Studies reviews detected absences. One from its form's Actions
// dropdown (Request justification), two at once from the list's action menu (Discard), and one
// through the Create absence wizard, also from the list, which prepares it for the teacher. Fixtures: test_absence_pending_tour.py.
function selectRow(name) {
    return {
        trigger: `.o_list_view .o_data_row:contains('${name}') .o_list_record_selector input`,
        content: `Select ${name}`,
        run: "click",
    };
}

function listAction(label) {
    return [
        { trigger: ".o_cp_action_menus button:has(.fa-cog)", content: "Open the list's action menu", run: "click" },
        { trigger: `.o-dropdown--menu .dropdown-item:contains('${label}')`, content: label, run: "click" },
    ];
}

registry.category("web_tour.tours").add("ems_absence_pending_review", {
    test: true,
    url: "/odoo/action-ems.action_absence_pending",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row:contains('Review Teacher A') td[name='date_from']",
            content: "The detected absences to review are listed: open one",
            run: "click",
        },
        ...clickAction("action_request_justification", "Request justification"),
        {
            trigger: ".o_form_view .o_field_widget[name='state'] .o_arrow_button_current[data-value='justification_requested']",
            content: "The teacher has been asked to justify it",
        },
        {
            trigger: ".o_breadcrumb .o_back_button a, .o_breadcrumb .breadcrumb-item a",
            content: "Back to the list",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('Review Teacher A') td[name='state'] .badge",
            content: "Still listed: it is not resolved yet",
        },
        selectRow("Review Teacher B"),
        selectRow("Review Teacher C"),
        ...listAction("Discard"),
        {
            trigger: ".o_list_view:not(:has(.o_data_row:contains('Review Teacher B'))):not(:has(.o_data_row:contains('Review Teacher C')))",
            content: "Both discarded and out of the list",
        },
        selectRow("Review Teacher D"),
        ...listAction("Create absence"),
        {
            trigger: ".modal .o_field_widget[name='holiday_status_id'] input",
            content: "Pick the absence type",
            run: "edit Justified",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Justified')",
            content: "Justified absence",
            run: "click",
        },
        {
            trigger: ".modal button[name='action_confirm']",
            content: "Create the absence",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal)) .o_list_view .o_data_row:contains('Review Teacher D') td[name='state']:contains('Absence prepared')",
            content: "Prepared for the teacher to send: still listed, not resolved yet",
        },
        // Issue #731: present for the first hour only, the rest stays to review.
        {
            trigger: ".o_list_view .o_data_row:contains('Review Teacher E') td[name='date_from']",
            content: "Open the one of the teacher who forgot to check in",
            run: "click",
        },
        ...clickAction("action_open_correct_check_in", "Correct check-in"),
        {
            trigger: ".modal .o_field_widget[name='date_to'] input",
            content: "Narrow it to the first hour, when the teacher was at the centre",
            async run(helpers) {
                await helpers.edit(this.anchor.value.replace("11:00", "10:00"));
            },
        },
        {
            trigger: ".modal button[name='action_confirm']",
            content: "Correct the check-in of that hour",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal)) .o_form_view .o_field_widget[name='date_from'] input:value(10:00)",
            content: "The rest, from 10:00, is still a detected absence to review",
        },
    ],
});

// Issue #735: the teacher reaches their detected absences to regularize from the Absences menu,
// without waiting for the reminder's link. Only the ones still asked by default: one already
// resolved is left out. Fixtures: test_absence_pending_tour.py.
registry.category("web_tour.tours").add("ems_absence_pending_teacher_menu", {
    test: true,
    steps: () => [
        {
            trigger: ".o_menu_sections button[data-menu-xmlid='hr_holidays.menu_hr_holidays_root']",
            content: "Absences is a dropdown for a teacher",
            run: "click",
        },
        {
            trigger: ".o-dropdown--menu .dropdown-item[data-menu-xmlid='hr_holidays.hr_leave_menu_my']",
            content: "With My Time Off in it",
        },
        {
            trigger: ".o-dropdown--menu .dropdown-item[data-menu-xmlid='ems.menu_absence_pending_mine']",
            content: "Absences to regularize",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row:only-child",
            content: "Only the one still to regularize",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell[name='state']",
            content: "Open it",
            run: "click",
        },
        ...clickAction("action_request_check_in_correction", "Its options are offered"),
        {
            trigger: ".modal .o_field_widget[name='absence_pending_id']",
            content: "The correction request opens",
        },
    ],
});

// Issue #735: a corrected entry shows the steps it went through, ending in Check-in corrected.
registry.category("web_tour.tours").add("ems_absence_pending_corrected", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_statusbar .o_field_widget[name='state']:has([data-value='justification_requested']) [data-value='corrected'].o_arrow_button_current",
            content: "Justification requested, then corrected, the current one",
        },
        {
            trigger: ".o_form_statusbar:not(:has([data-value='linked'])):not(:has([data-value='pending']))",
            content: "Nothing after it, and no review step for the teacher",
        },
    ],
});

// Issue #735: the Head of Studies refuses the absence the teacher sent from the one prepared for
// them; the detected absence is claimed again. Fixtures: test_absence_pending_tour.py.
registry.category("web_tour.tours").add("ems_absence_pending_refuse_request", {
    test: true,
    steps: () => [
        ...clickAction("action_refuse", "Refuse the teacher's absence request"),
        {
            trigger: ".modal div[name='message'] textarea",
            content: "Say why",
            run: "edit Tour it does not justify it",
        },
        {
            trigger: ".modal-footer button[name='action_confirm'], .modal-footer .btn-primary",
            content: "Confirm the refusal",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal)) .o_form_view .alert-danger .o_field_widget[name='ems_refusal_reason']",
            content: "Refused, with its reason",
        },
    ],
});

registry.category("web_tour.tours").add("ems_absence_pending_reopened", {
    test: true,
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row:contains('Tour Pending Teacher') .o_field_widget[name='state'] .badge",
            content: "The detected absence is back on the Head of Studies' list, to review",
        },
    ],
});
