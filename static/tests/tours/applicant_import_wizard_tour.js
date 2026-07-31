/** @odoo-module **/

import { registry } from "@web/core/registry";
import { inputFiles } from "@web/../tests/utils";

const HEADERS = [
    'Ident. RALC', 'Nom', 'Primer cognom', 'Segon cognom', 'Telèfon', 'Correu electrònic',
    'Centre assignat', 'Codi ensenyament assignat', 'Nom ensenyament assignat', 'Torn assignat',
];
const ROW = [
    '1234567890', 'Tour', 'Applicant', 'Wizard', '600111222', 'tour.applicant@example.com',
    '8028047', 'CFPM    ZZ99', 'Test Study (Applicant Import Wizard Tour)', 'Matí',
];

function csvContent() {
    const escape = (value) => `"${value.replace(/"/g, '""')}"`;
    return [HEADERS, ROW].map((row) => row.map(escape).join(',')).join('\n');
}

// ems.applicant_import_wizard: widget="binary" file upload had zero browser coverage - the
// Binary field's real upload target is a hidden <input type="file"> (see
// web/static/src/views/fields/file_handler.xml), which the generic tour "click"/"edit"
// actions can't drive at all. Odoo's own tour test utilities provide inputFiles() for
// exactly this (see e.g. sale's mail_attachment_removal_test_tour.js).
// Opened via the Preinscription list's own cog-menu entry (import_gedac_cog_menu.js), the
// real path a user takes - not a direct URL to the wizard's own action, which only ever
// proved the wizard form itself works, never that the cog-menu click (a raw <DropdownItem>,
// not Odoo's own .o_menu_item wrapper - see working_schedules_import_wizard_tour.js for the
// same gotcha) actually opens it.
registry.category("web_tour.tours").add("ems_applicant_import_wizard_upload", {
    test: true,
    url: "/odoo/action-ems.action_ems_applicants",
    steps: () => [
        { trigger: ".o_list_view", content: "Preinscription list loaded" },
        {
            trigger: ".o_cp_action_menus button",
            content: "Open the list's Actions (cog) menu",
            run: "click",
        },
        {
            trigger: ".dropdown-item:contains('Import from GEDAC')",
            content: "Click 'Import from GEDAC'",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='file']",
            content: "Import wizard loaded",
            run: async () => {
                const file = new File([csvContent()], "gedac.csv", { type: "text/csv" });
                await inputFiles(".o_field_widget[name='file'] .o_input_file", [file]);
            },
        },
        {
            // OWL doesn't sync an <input>'s live value to the HTML "value" attribute (see
            // CLAUDE.md's tour-testing conventions) - hoot-dom's :value() pseudo-class reads
            // the real DOM property instead of a plain [value=...] attribute selector.
            trigger: ".o_field_widget[name='file'] input.o_input:value(gedac.csv)",
            content: "File attached",
        },
        {
            // target="new" dialog - footer is a sibling of .o_form_view, not nested under
            // it (see the same gotcha documented in grade_session_state_wizard_tour.js).
            trigger: ".modal footer button[name='action_import']",
            content: "Import applicants",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='result_html']",
            content: "Import result rendered",
        },
    ],
});
