/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #511: a student's form splits its notes into "Public notes (teachers)" (res.partner.comment,
// read by every teacher) and "Private notes (tutoring)" (res.partner.private_notes, only the tutor,
// the chiefs above them, guidance, coexistence and the academic admin). Tabs are matched by their
// name attribute, never by their (translatable) label.
registry.category("web_tour.tours").add("ems_student_private_note_tutor", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .o_notebook .nav-link[name='public_notes']",
            content: "Open the public notes tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='comment'] .odoo-editor-editable:contains('Public tour note')",
            content: "The public notes are shown",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link[name='private_notes']",
            content: "The tutor sees the private notes tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='private_notes'] .odoo-editor-editable p",
            content: "The tutor writes a private note",
            run: "editor Written by the tutor",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_saved",
            content: "Saved",
        },
    ],
});

registry.category("web_tour.tours").add("ems_student_private_note_teacher", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .o_notebook .nav-link[name='public_notes']",
            content: "Open the public notes tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='comment']:contains('Public tour note')",
            content: "Any teacher reads the public notes",
        },
        {
            trigger: ".o_form_view .o_notebook:not(:has(.nav-link[name='private_notes']))",
            content: "A teacher outside the tutoring team never sees the private notes tab",
        },
    ],
});
