/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #774 - the Erasmus team pastes a prepared information card (Bootstrap classes) into the
// text the portal shows: the call's "Information for applicants" and the group mobility's
// "Information for students". Records seeded by tests/test_erasmus_info_codeview_tour.py.
// Structural selectors only, so the user's language does not matter.

const CARD = '<div class="card border-primary"><div class="card-body">' +
    '<h5 class="card-title">Tour card</h5><p class="card-text">Prepared elsewhere</p></div></div>';

const FIELD = ".o_form_view .o_field_widget[name='description']";

/** Paste the card through the code view, back to the editor, and save. */
function pasteCardSteps() {
    return [
        {
            trigger: `${FIELD} .note-editable`,
            content: "Click in the text: the editor's toolbar fills in",
            run: "click",
        },
        {
            trigger: `${FIELD} .o-we-toolbar button[name='codeview']`,
            content: "The code view is in the editor's toolbar, without developer mode",
            run: "click",
        },
        {
            trigger: `${FIELD} textarea.o_codeview`,
            content: "Paste the card's HTML",
            run: `edit ${CARD}`,
        },
        {
            trigger: `${FIELD} #codeview-btn-group button`,
            content: "Back to the editor",
            run: "click",
        },
        {
            trigger: `${FIELD} .note-editable .card.border-primary .card-body .card-title`,
            content: "The editor shows the card with its classes",
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
    ];
}

registry.category("web_tour.tours").add("ems_erasmus_call_info_codeview", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_call",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='name']:contains('Test Erasmus Call')",
            content: "Open the call from the list",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook a.nav-link[name='description']",
            content: "Open the Information for applicants tab",
            run: "click",
        },
        ...pasteCardSteps(),
    ],
});

registry.category("web_tour.tours").add("ems_erasmus_group_info_codeview", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_group_mobility",
    steps: () => [
        {
            trigger: ".o_kanban_view .o_kanban_record:contains('Test SMX2 morning')",
            content: "The mobility's card in the overview",
        },
        {
            trigger: ".o_control_panel .o_switch_view.o_list",
            content: "Switch to the list",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row td[name='name']:contains('Test SMX2 morning')",
            content: "Open the mobility from the list",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook a.nav-link[name='enrolment']",
            content: "Open the Enrolment tab",
            run: "click",
        },
        ...pasteCardSteps(),
    ],
});
