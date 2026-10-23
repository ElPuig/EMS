/** @odoo-module **/

import { registry } from "@web/core/registry";
import { clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

// Issue #686 - the Erasmus+ staff call. Every tour runs against records seeded by
// tests/test_erasmus_staff_tour.py and uses structural selectors (field names, values, CSS
// classes), so the logged-in user's language does not matter.

function attachFile(selector, name) {
    const transfer = new DataTransfer();
    transfer.items.add(new File(["%PDF-1.4 tour"], name, { type: "application/pdf" }));
    const input = document.querySelector(selector);
    input.files = transfer.files;
    input.dispatchEvent(new Event("change", { bubbles: true }));
}

// A teacher applies to the staff call from the portal: activity, host, the identity document and
// the mobility plan.
registry.category("web_tour.tours").add("ems_portal_erasmus_staff_apply", {
    test: true,
    url: "/my/erasmus",
    steps: () => [
        {
            trigger: ".o_ems_erasmus_call a.o_ems_erasmus_apply",
            content: "The open staff call offers to apply",
            run: "click",
        },
        {
            trigger: "form.o_ems_erasmus_form .o_ems_erasmus_staff_form select[name='staff_activity']",
            content: "Choose the activity",
            run: "select job_shadowing",
        },
        {
            trigger: "form.o_ems_erasmus_form input[name='host_entity']",
            content: "Name the host entity",
            run: "edit Tour host school",
        },
        {
            trigger: "form.o_ems_erasmus_form input[name='declared_never_staff_mobility']",
            content: "Never had a staff mobility",
            run: "click",
        },
        {
            trigger: "form.o_ems_erasmus_form input[name='declared_centre_start_date']",
            content: "At the centre since September 2015",
            run() {
                this.anchor.value = "2015-09";
            },
        },
        {
            trigger: "form.o_ems_erasmus_form textarea[name='plan_reason']",
            content: "Write the mobility plan (annex 1)",
            run() {
                for (const name of ["plan_reason", "plan_objectives", "plan_application"]) {
                    document.querySelector(`form.o_ems_erasmus_form textarea[name='${name}']`).value = `Tour ${name}`;
                }
                for (const name of ["destination", "preferred_dates"]) {
                    document.querySelector(`form.o_ems_erasmus_form input[name='${name}']`).value = `Tour ${name}`;
                }
            },
        },
        {
            trigger: "form.o_ems_erasmus_form .o_ems_erasmus_document.o_ems_erasmus_required input[type='file']",
            content: "Attach the required documents",
            run() {
                const inputs = document.querySelectorAll(
                    "form.o_ems_erasmus_form .o_ems_erasmus_document.o_ems_erasmus_required input[type='file']");
                inputs.forEach((input, index) => {
                    input.setAttribute("data-tour-index", index);
                    attachFile(`input[data-tour-index='${index}']`, `document${index}.pdf`);
                });
            },
        },
        {
            trigger: "form.o_ems_erasmus_form button[name='submit']",
            content: "Submit the application",
            run: "click",
        },
        {
            trigger: ".o_ems_erasmus_application.o_ems_erasmus_state_submitted",
            content: "It is listed as submitted",
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
            trigger: ".o_form_view .o_field_widget[name='plan_objectives']:contains('Test objectives')",
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
