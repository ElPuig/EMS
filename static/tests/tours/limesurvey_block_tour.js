/** @odoo-module **/

import { registry } from "@web/core/registry";

// widget="code" (tsv_raw_text, both header and block forms) renders via the Ace editor
// library - its keyboard-capture textarea is deliberately invisible, and the tour engine's
// generic "edit" action doesn't know how to drive it. Odoo core's own tours (e.g.
// addons/test_website/static/tests/tours/reset_views.js) fill an Ace editor via the global
// `ace` object directly instead - same pattern here.
function fillAceEditor(fieldSelector, text) {
    return {
        trigger: `${fieldSelector} .ace_editor`,
        content: `Fill in ${fieldSelector} (Ace code editor)`,
        run: (helpers) => {
            ace.edit(helpers.anchor).setValue(text, -1);
        },
    };
}

// ems.limesurvey_block's form is only ever reached embedded inside a header's own form (a
// non-editable one2many list -> opens the block's own registered form in a modal dialog, a
// "form within a form"). No tour previously covered this path at all - added when
// special_wpi_enrolled/special_subject_enrolled (two Booleans) were replaced by special_type
// (a Selection, widget="radio") to actually confirm the new radio widget renders and saves
// correctly in a real browser, not just that ./upgrade.sh's XML/field validation passes.
registry.category("web_tour.tours").add("ems_limesurvey_block_special_type", {
    test: true,
    url: "/odoo/action-ems.action_limesurvey_header_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Surveys list view loaded",
        },
        {
            trigger: ".o_list_button_add",
            content: "Click New to create a survey header",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='name'] input",
            content: "Fill in name",
            run: "edit Tour Survey Header",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='title'] input",
            content: "Fill in title",
            run: "edit Tour Survey Title",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='description'] input",
            content: "Fill in description",
            run: "edit Tour Survey Description",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='target'] select",
            content: "Pick target = Students",
            // Odoo's SelectionField JSON-stringifies the option value attribute, so
            // "select students" doesn't match the raw key - select by visible label instead.
            run: "selectByLabel Students",
        },
        fillAceEditor(".o_form_view .o_field_widget[name='tsv_raw_text']", "col\n{'TITLE'}"),
        {
            trigger: ".o_form_button_save",
            content: "Save the survey header",
            run: "click",
        },
        {
            trigger: ".o_notebook .nav-link:contains('Blocks')",
            content: "Open the Blocks tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='limesurvey_block_ids'] a:contains('Add a line')",
            content: "Add a new block (opens the block's own form in a dialog)",
            run: "click",
        },
        {
            trigger: ".modal .o_form_view .o_field_widget[name='name'] input",
            content: "Block form opened in a dialog",
            run: "edit Tour Block",
        },
        fillAceEditor(".modal .o_form_view .o_field_widget[name='tsv_raw_text']", "col\nval"),
        {
            trigger: ".modal .o_form_view .o_field_widget[name='special'] input[type='checkbox']",
            content: "Enable 'Special behaviour' to reveal the special_type radio group",
            run: "click",
        },
        {
            trigger: ".modal .o_form_view .o_field_widget[name='special_type'] label:contains('WorkPlace Internship')",
            content: "Select the 'WorkPlace Internship' radio option",
            run: "click",
        },
        {
            trigger: ".modal .o_form_view .o_field_widget[name='special_type'] input[type='radio']:checked",
            content: "Radio option is actually selected (not just clicked)",
        },
        {
            trigger: ".modal .o_form_button_save",
            content: "Save the block dialog",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='limesurvey_block_ids']:not(:has(.modal)) .o_data_row td[name='name']:contains('Tour Block')",
            content: "New block confirmed in the embedded list after the dialog closed",
        },
        {
            trigger: ".o_field_widget[name='limesurvey_block_ids'] .o_data_row td[name='name']:contains('Tour Block')",
            content: "Re-open the block to confirm special_type persisted",
            run: "click",
        },
        {
            trigger: ".modal .o_form_view .o_field_widget[name='special_type'] input[data-value='wpi']:checked",
            content: "special_type is still 'wpi' after reopening — persisted correctly",
        },
        {
            trigger: ".modal .o_form_button_save, .modal button:contains('Discard')",
            content: "Close the block dialog again",
            run: "click",
        },
        {
            trigger: ".o_form_view:not(:has(.modal)) .o_field_widget[name='limesurvey_block_ids']",
            content: "Back on the header form, no modal left open — no client-side error",
        },
        {
            // Reopening the block's dialog leaves the header form itself dirty again (the
            // x2many relation is a pending change until the parent is saved) - save it so
            // the tour doesn't end with an unsaved form (Odoo's test harness fails the tour
            // for that, separately from step-by-step success).
            trigger: ".o_form_button_save",
            content: "Save the header form to leave a clean state",
            run: "click",
        },
        {
            trigger: ".o_form_view:not(.o_dirty) .o_field_widget[name='limesurvey_block_ids']",
            content: "Header form saved, no pending edition left",
        },
    ],
});
