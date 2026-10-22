/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issues #676, #688: the Department Chief sets the other half of a split group on one half's form.
// That half has another tutor: the form asks, and the chief keeps it (co-tutors). The delegate,
// picked among the other half's students, reaches it without asking, since it had none. Then the
// chief changes the tutor and replicates it to the other half. Seed data and the checks on both
// halves come from TestGroupJoinsWithTour.
registry.category("web_tour.tours").add("ems_group_joins_with", {
    test: true,
    url: "/odoo/action-ems.action_group_tree",
    steps: () => [
        {
            trigger: ".o_searchview_input",
            content: "Search for the seeded halves",
            run: "edit TJWG1",
        },
        {
            trigger: ".o_searchview_input",
            content: "Confirm the search",
            run: "press Enter",
        },
        {
            trigger: ".o_list_view .o_data_row td:contains('TJWG1A')",
            content: "Open the first half",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='joinable_group_ids'] input",
            content: "Type the other half",
            run: "edit TJWG1B",
        },
        {
            trigger: ".o-autocomplete--dropdown-item a:contains('TJWG1B')",
            content: "Pick it",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='joinable_group_ids'] .o_tag:contains('TJWG1B')",
            content: "It is now its other half",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".modal .modal-body:contains('TJWG1B: Tutor Tour Joins With Tutor 2 will be replaced by Tour Joins With Tutor 1.')",
            content: "The form asks before replacing the other half's tutor",
        },
        {
            trigger: ".modal .modal-footer .btn-secondary",
            content: "Keep each half's own tutor",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_saved",
            content: "Saved",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='delegate_id'] input",
            content: "Look for a student of the other half as delegate",
            run: "edit Tour Joins With Student",
        },
        {
            trigger: ".o-autocomplete--dropdown-item a:contains('Tour Joins With Student')",
            content: "The other half's students can be chosen",
            run: "click",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_saved",
            content: "Saved without asking: the other half had no delegate",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='tutor_id'] input",
            content: "Change the tutor",
            run: "edit Tour Joins With Tutor 3",
        },
        {
            trigger: ".o-autocomplete--dropdown-item a:contains('Tour Joins With Tutor 3')",
            content: "Pick the new tutor",
            run: "click",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".modal .modal-body:contains('TJWG1B: Tutor Tour Joins With Tutor 2 will be replaced by Tour Joins With Tutor 3.')",
            content: "The form asks before replacing the other half's tutor",
        },
        {
            trigger: ".modal .modal-footer .btn-primary",
            content: "Replicate it",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_saved",
            content: "Saved",
        },
    ],
});
