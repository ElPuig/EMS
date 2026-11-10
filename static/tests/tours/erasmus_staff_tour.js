/** @odoo-module **/

import { registry } from "@web/core/registry";
import { inputFiles } from "@web/../tests/utils";
import { clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

// Issue #686 - the Erasmus+ staff call. Every tour runs against records seeded by
// tests/test_erasmus_staff_tour.py and uses structural selectors (field names, values, CSS
// classes), so the logged-in user's language does not matter.

// The 2026-11-04 review: a teacher applies to the staff call in the backend (never the portal):
// Staff calls, Apply, the form in its dialog, the identity document, Submit, and My applications.
// The tour's user writes in English (tests/test_erasmus_staff_tour.py), for the date fields.
const STAFF_CALL = "Test Erasmus Staff Call";

registry.category("web_tour.tours").add("ems_erasmus_staff_backend_apply", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_staff_calls",
    steps: () => [
        {
            trigger: `.o_list_view .o_data_row td[name='name']:contains('${STAFF_CALL}')`,
            content: "The open staff call is listed",
            run: "click",
        },
        ...clickAction("action_staff_apply", "Apply"),
        {
            trigger: ".o_form_view .o_ems_erasmus_staff_next",
            content: "The application says what to do now",
        },
        ...clickAction("action_staff_edit", "Fill in the form"),
        {
            trigger: ".modal .o_field_widget[name='proposal_a'] textarea",
            content: "Proposal A, in your own words",
            run: "edit Job shadowing at the Tour host school, in April",
        },
        {
            trigger: ".modal .o_field_widget[name='proposal_b'] textarea",
            content: "Proposal B, the backup",
            run: "edit An English course in Malta, in July",
        },
        {
            trigger: ".modal .o_field_widget[name='plan_text'] textarea",
            content: "What you want to learn and how you will apply it (annex 1)",
            run: "edit Tour plan_text",
        },
        {
            trigger: ".modal .o_field_widget[name='declared_never_staff_mobility'] input",
            content: "Never had a staff mobility",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='declared_centre_start_date'] input",
            content: "At the centre since September 2015",
            run: "edit 09/17/2015",
        },
        {
            trigger: ".modal-footer button[name='action_save']",
            content: "Save the form",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal)) .o_form_view .o_field_widget[name='proposal_a']:contains('Tour host school')",
            content: "The answers are on the application",
        },
        {
            trigger: ".o_form_view .o_notebook a[name='documents']",
            content: "Open the documents",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='document_ids'] .o_data_row:contains('Identity document') button[name='action_staff_upload']",
            content: "Hand in the identity document",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='attachment_ids']",
            content: "Attach the file",
            run: async () => {
                const file = new File(["%PDF-1.4 tour"], "id.pdf", { type: "application/pdf" });
                await inputFiles(".modal .o_field_widget[name='attachment_ids'] .o_input_file", [file]);
            },
        },
        {
            trigger: ".modal .o_field_widget[name='attachment_ids'] .o_attachment",
            content: "File attached",
        },
        {
            trigger: ".modal-footer button[name='action_confirm']",
            content: "Hand it in",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal)) .o_form_view .o_field_widget[name='document_ids'] .o_data_row:contains('Identity document') .o_attachment",
            content: "The document has its file",
        },
        ...clickAction("action_staff_submit", "Submit the application"),
        {
            trigger: ".modal-footer .btn-primary",
            content: "Confirm",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_statusbar_status button[data-value='submitted'].o_arrow_button_current",
            content: "The application is submitted",
        },
        {
            trigger: ".o_form_view",
            content: "Go to My applications",
            run() {
                window.location.href = "/odoo/action-ems.action_erasmus_my_applications";
            },
        },
        {
            trigger: `.o_list_view .o_data_row td[name='call_id']:contains('${STAFF_CALL}')`,
            content: "It is listed under My applications",
        },
    ],
});

// A selected teacher who accepted the place sends their activity proposal from My mobilities.
registry.category("web_tour.tours").add("ems_erasmus_staff_backend_mobility", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_my_mobilities",
    steps: () => [
        {
            trigger: `.o_list_view .o_data_row td[name='call_id']:contains('${STAFF_CALL}')`,
            content: "The mobility is listed",
            run: "click",
        },
        ...clickAction("action_staff_propose", "Send the activity proposal"),
        {
            // Selection values are JSON-encoded in the <select>, hence the quotes.
            trigger: ".modal .o_field_widget[name='proposal_activity'] select",
            content: "A structured course",
            run: 'select "course"',
        },
        {
            trigger: ".modal .o_field_widget[name='proposal_host'] input",
            content: "The course provider",
            run: "edit Tour Course Provider",
        },
        {
            trigger: ".modal .o_field_widget[name='proposal_date_start'] input",
            content: "From",
            run: "edit 07/05/2027",
        },
        {
            trigger: ".modal .o_field_widget[name='proposal_date_end'] input",
            content: "To",
            run: "edit 07/09/2027",
        },
        {
            trigger: ".modal .o_field_widget[name='leave_declaration'] input",
            content: "The responsible declaration",
            run: "click",
        },
        {
            trigger: ".modal-footer button[name='action_confirm']",
            content: "Send the proposal",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal)) .o_form_view .o_field_widget[name='proposal_host']:contains('Tour Course Provider')",
            content: "The proposal waits for the Direction",
        },
    ],
});

// A panel member (a plain teacher) rates a mobility plan from Erasmus+ > My plan ratings.
registry.category("web_tour.tours").add("ems_erasmus_my_plan_rating", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_my_plan_ratings",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='partner_id']:contains('Erasmus Staff 1')",
            content: "The plan to rate is listed",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='plan_text']:contains('Test plan')",
            content: "The mobility plan is on screen",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='relevance'] input[data-value='1']",
            content: "Relevance and concreteness: 1",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='transfer'] input[data-value='0.5']",
            content: "Application and dissemination: 0.5",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='score']:contains('1.5')",
            content: "The rating adds up",
        },
        ...clickAction("action_submit", "Submit the rating"),
        {
            trigger: ".o_form_view .o_statusbar_status button[data-value='submitted'].o_arrow_button_current",
            content: "The rating is submitted",
        },
    ],
});

// The Erasmus team records the staff criteria and a merit on the application's Scoring tab.
registry.category("web_tour.tours").add("ems_erasmus_staff_scoring", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_application",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='partner_id']:contains('Erasmus Staff 1')",
            content: "The admitted staff application is listed",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook a[name='staff_scoring']",
            content: "Open the staff scoring tab",
            run: "click",
        },
        {
            // Selection values are JSON-encoded in the <select>, hence the quotes.
            trigger: ".o_form_view .o_field_widget[name='last_staff_mobility'] select",
            content: "Last staff mobility: more than two courses ago",
            run: 'select "older"',
        },
        {
            trigger: ".o_form_view .o_notebook .o_field_widget[name='language_level'] select",
            content: "C1 certificate",
            run: 'select "c1"',
        },
        {
            trigger: ".o_form_view .o_field_widget[name='seniority'] select",
            content: "Seniority: 2 to 5 years",
            run: 'select "y2"',
        },
        {
            trigger: ".o_form_view .o_field_widget[name='merit_ids'] .o_field_x2many_list_row_add a",
            content: "Add a merit",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='merit_ids'] .o_data_row .o_field_widget[name='kind'] select",
            content: "A project coordination",
            run: 'select "project_coordination"',
        },
        {
            trigger: ".o_form_view .o_field_widget[name='merit_ids'] .o_data_row .o_field_widget[name='description'] input",
            content: "Its justification",
            run: "edit Tour project",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='merits_checked'] input",
            content: "Every merit is recorded",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_saved",
            content: "Saved",
        },
    ],
});

// The Erasmus team opens the staff call: its panel, sends the plans to the panel and opens the
// ranking.
registry.category("web_tour.tours").add("ems_erasmus_staff_call", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_call",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='name']:contains('Test Erasmus Staff Call')",
            content: "The staff call is listed",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook a[name='panel']",
            content: "Open the panel tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='panel_ids'] .o_data_row",
            content: "The panel is listed",
        },
        ...clickAction("action_send_to_panel", "Send the plans to the panel"),
        {
            trigger: ".o_form_view button[name='action_view_ranking']",
            content: "Open the ranking",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='score_plan']",
            content: "The staff ranking lists the staff criteria",
        },
    ],
});

// The team's Plan ratings screen opens, list and form.
registry.category("web_tour.tours").add("ems_erasmus_plan_ratings", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_plan_rating",
    steps: () => [
        {
            trigger: ".o_list_view .o_group_header:contains('Erasmus Staff 1')",
            content: "One row per applicant",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='partner_id']:contains('Erasmus Staff 1')",
            content: "The ratings are listed",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='panel_member_id']",
            content: "The rating form opens",
        },
    ],
});
