/** @odoo-module **/

import { registry } from "@web/core/registry";
import { checkActions, clickAction, clickListHeaderAction } from "./actions_dropdown_helpers";

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
            content: "It is to review: the chief who entered it leaves that to the Head of Studies (issue #707)",
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

// Issue #707: the Head of Studies reviews the detected absences of their teachers - several at
// once from the list (the selection's Actions dropdown, here "Create absence" and its wizard), one
// from its form (the form's Actions dropdown, here "Request justification").
registry.category("web_tour.tours").add("ems_absence_pending_review", {
    test: true,
    url: "/odoo/action-ems.action_absence_pending",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row:contains('Tour Review Teacher') td[name='state'] .badge",
            content: "The list opens on what is to review",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('Tour Review Teacher') .o_list_record_selector input",
            content: "Select the first teacher's detected absence",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('Tour Review Second Teacher') .o_list_record_selector input",
            content: "And the second one's",
            run: "click",
        },
        ...clickListHeaderAction("action_prepare_absence", "Create the absence for both"),
        {
            trigger: ".modal .o_field_widget[name='leave_type_id'] .form-check:contains('Justified absence') input",
            content: "Choose the absence type",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button[name='action_confirm']",
            content: "Prepare the absence",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal)) .o_list_view:not(:has(.o_data_row:contains('Tour Review Teacher')))",
            content: "Both are no longer to review: each teacher has to check and send their request",
        },
        {
            // Not the teacher's cell: its avatar opens the employee's card instead of the record.
            trigger: ".o_list_view .o_data_row:contains('Tour Review Third Teacher') td[name='date_from']",
            content: "Open the third one",
            run: "click",
        },
        ...checkActions({
            offered: ["action_request_justification", "action_correct_check_in", "action_prepare_absence", "action_discard"],
            notOffered: ["action_request_absence"],
        }, "The four review actions are offered, not the teacher's own request"),
        ...clickAction("action_request_justification", "Request justification"),
        {
            trigger: ".o_form_view .o_field_widget[name='state'] .o_arrow_button_current[data-value='justification_requested']",
            content: "The teacher has been asked",
        },
        {
            trigger: ".o_form_view:not(:has(.o_ems_actions_toggle)):not(:has(.o_form_statusbar button[name='action_discard']))",
            content: "Nothing is left to review on it",
        },
    ],
});

// Issue #696: the teacher opens their own detected absence from the reminder's link and
// requests it from there (issue #707: once they have been asked).
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
    ],
});
