/** @odoo-module **/

import { registry } from "@web/core/registry";
import { inputFiles } from "@web/../tests/utils";
import { clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

// Issue #686 - the Erasmus+ staff call. Every tour runs against records seeded by
// tests/test_erasmus_staff_tour.py and uses structural selectors (field names, values, CSS
// classes), so the logged-in user's language does not matter.

// The 2026-11-04 review: a teacher applies to the staff call in the backend (never the portal):
// Staff calls, Apply (the form's dialog opens straight away, issue #802), the identity document,
// Submit, and My applications.
// The tour's user writes in English (tests/test_erasmus_staff_tour.py), for the date fields.
const STAFF_CALL = "Test Erasmus Staff Call";

// Issue #810: a list whose last column (the "Hand in"/"PDF" buttons) spilled over its right edge.
function listFits(field) {
    return {
        trigger: `.o_form_view .o_field_widget[name='${field}'] .o_list_renderer`,
        content: "The whole list fits, its buttons included",
        run() {
            const renderer = document.querySelector(`.o_form_view .o_field_widget[name='${field}'] .o_list_renderer`);
            if (renderer.scrollWidth > renderer.clientWidth + 1) {
                throw new Error(`The ${field} list is wider than the form: ${renderer.scrollWidth} > ${renderer.clientWidth}`);
            }
        },
    };
}

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
        // Issue #802: nothing filled in yet, so the form's dialog opens straight away.
        {
            // Issue #810: every field shows its line and an example of what to write.
            trigger: ".modal .o_field_highlight .o_field_widget[name='proposal_a'] textarea[placeholder]",
            content: "The empty form shows where and what to write",
        },
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
            // P03: both buttons, sending is the highlighted one.
            trigger: ".modal-footer:has(button[name='action_save'].btn-secondary) button[name='action_save_submit'].btn-primary",
            content: "Save and submit is the highlighted button",
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
            // Issue #810: only what the applicant handed in and what is left to do, nothing of the
            // team's review before submitting.
            trigger: ".o_form_view .o_field_widget[name='document_ids'] table:has(th[data-name='current_attachment_ids']):has(td[name='todo_state']):not(:has(th[data-name='attachment_ids'])):not(:has(th[data-name='review_state'])):not(:has(th[data-name='review_comment']))",
            content: "The applicant's columns only",
        },
        listFits("document_ids"),
        {
            trigger: ".o_form_view .o_field_widget[name='document_ids'] .o_data_row:contains('Identity document') button[name='action_staff_upload']",
            content: "Hand in the identity document",
            run: "click",
        },
        {
            trigger: ".modal .o_form_view p.text-muted",
            content: "The dialog says which files it expects",
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
        // Issue #786: while the application can be changed, filling in the form is the one action
        // (a plain button), and its dialog submits it.
        {
            trigger: ".o_form_view .o_form_statusbar:not(:has(.o_ems_actions_toggle)) button[name='action_staff_edit']",
            content: "Fill in the form is the one action, in view",
            run: "click",
        },
        {
            trigger: ".modal-footer button[name='action_save_submit']",
            content: "Save and submit the application",
            run: "click",
        },
        {
            trigger: ".modal:has(.modal-body:contains('Submit the application?')) .modal-footer .btn-primary",
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
        {
            // Issue #810: only what the teacher hands in, in words; no empty columns of the team.
            trigger: ".o_form_view .o_field_widget[name='staff_record_summary']:contains('You have handed in 0 of')",
            content: "The record says what the teacher has handed in",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='document_ids'] table:has(td[name='todo_state']):not(:has(th[data-name='review_comment'])):not(:has(th[data-name='prepared_attachment_ids']))",
            content: "No empty team columns",
        },
        ...clickAction("action_staff_propose", "Send the activity proposal"),
        {
            trigger: ".modal .o_field_widget[name='proposal_activity'] select:has(option:checked:contains('E.g.'))",
            content: "The activity has an example too (issue #810), greyed like the others",
            run() {
                const select = document.querySelector(".modal .o_field_widget[name='proposal_activity'] select");
                const input = document.querySelector(".modal .o_field_widget[name='proposal_host'] input");
                const example = getComputedStyle(select).color;
                const placeholder = getComputedStyle(input, "::placeholder").color;
                if (example !== placeholder) {
                    throw new Error(`The activity's example is ${example}, not the examples' ${placeholder}`);
                }
            },
        },
        {
            trigger: ".modal .o_field_highlight .o_field_widget[name='proposal_host'] input[placeholder]",
            content: "The empty proposal shows where and what to write (issue #810)",
        },
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
            run() {
                window.location.href = "/odoo/action-ems.action_erasmus_my_applications";
            },
        },
        {
            trigger: `.o_list_view .o_data_row td[name='call_id']:contains('${STAFF_CALL}')`,
            content: "Open the application",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook a[name='results']",
            content: "Its results",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='resolution_line_ids'] .o_data_row button[name='action_staff_download']",
            content: "Each list can be downloaded",
        },
        listFits("resolution_line_ids"),
    ],
});

// Issue #810: the teacher reads their grant in their mobility: due, paid and still to receive.
registry.category("web_tour.tours").add("ems_erasmus_staff_grant", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .o_notebook a[name='grant']",
            content: "The grant tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='grant_net']:contains('1,000.00')",
            content: "What the teacher is due",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='grant_to_receive']:contains('1,000.00')",
            content: "Nothing paid yet: all of it still to receive",
        },
        {
            trigger: ".o_form_view:not(:has(.o_field_widget[name='payment_ids'])):not(:has(.o_field_widget[name='provision_ids']))",
            content: "Neither the payments nor the invoices' shares",
        },
    ],
});

// Issue #810: a staff call's resolution, as the Erasmus team prepares it: no modality column (the
// staff have none since #772), and the score header is not cut.
registry.category("web_tour.tours").add("ems_erasmus_staff_resolution", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .o_field_widget[name='line_ids'] table:has(th[data-name='score_total']):not(:has(th[data-name='modality_id'])) .o_data_row",
            content: "The staff resolution lists ranks, people and scores, without modalities",
        },
        listFits("line_ids"),
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
            // Issue #810: each text at full width under its title, not squeezed into a label column.
            trigger: ".o_form_view div[name='plan']:not(.o_inner_group) .o_field_widget[name='plan_text']:contains('Test plan')",
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
