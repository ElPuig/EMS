/** @odoo-module **/

import { registry } from "@web/core/registry";
import { inputFiles } from "@web/../tests/utils";

// A minimal but structurally real .xlsx (Esfera/SAGA header row: 'Grup Classe' + 'Nom' plus
// one data row) - pre-built with openpyxl (see this repo's own test fixture pattern in
// test_student_import_wizard.py) and embedded as base64, since a valid xlsx is a real zip
// container that can't be hand-authored as a plain JS string the way a CSV can. Missing most
// of the ~35 columns Esfera actually exports, this deterministically hits action_import()'s
// "missing required columns" UserError - a real, legitimate path to verify, and one that
// doesn't require faithfully replicating the full Esfera export format just to prove the
// widget="binary" upload and the import button both work in a real browser.
const XLSX_B64 = "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";

function base64ToFile(b64, name, type) {
    const binary = atob(b64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
    }
    return new File([bytes], name, { type });
}

// Opened via the Students list's own cog-menu entry (import_student_cog_menu.js), the real
// path a user takes - not a direct URL to the wizard's own action, which only ever proved the
// wizard form itself works, never that the cog-menu click (a raw <DropdownItem>, not Odoo's
// own .o_menu_item wrapper) actually opens it.
registry.category("web_tour.tours").add("ems_student_import_wizard_missing_columns", {
    test: true,
    url: "/odoo/action-ems.action_student_kanban",
    steps: () => [
        { trigger: ".o_control_panel", content: "Educational Community loaded" },
        {
            trigger: ".o_cp_action_menus button",
            content: "Open the list's Actions (cog) menu",
            run: "click",
        },
        {
            trigger: ".dropdown-item:contains('Import from Esfera')",
            content: "Click 'Import from Esfera'",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='file']",
            content: "Import wizard loaded",
            run: async () => {
                const file = base64ToFile(XLSX_B64, "esfera.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
                await inputFiles(".o_field_widget[name='file'] .o_input_file", [file]);
            },
        },
        {
            trigger: ".o_field_widget[name='file'] input.o_input:value(esfera.xlsx)",
            content: "File attached",
        },
        {
            trigger: ".modal footer button[name='action_import']",
            content: "Import students",
            run: "click",
        },
        {
            trigger: ".o_error_dialog:contains('missing required columns')",
            content: "The missing-columns validation surfaces as a real error dialog",
        },
    ],
});

// A full xlsx with every one of _REQUIRED_COLUMNS actually filled in (built the same way as
// test_student_import_wizard.py::test_action_import_end_to_end_creates_student, which already
// proves the Python side works) - unlike the tour above, this drives a genuine successful
// import all the way through the real upload UI, never verified in a browser before. The
// student ("Esfera Success Tour Student") and its tutor ("Fictitious Tutor", deduced as
// "Mare" -> relation_type_mother) are seeded fresh here, matched to a group whose
// external_id ('ESFERA-TOUR-A') mirrors the 'Grup Classe' cell - see test_student_import_wizard_tour.py.
const XLSX_SUCCESS_B64 = "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";

registry.category("web_tour.tours").add("ems_student_import_wizard_success", {
    test: true,
    url: "/odoo/action-ems.action_student_kanban",
    steps: () => [
        { trigger: ".o_control_panel", content: "Educational Community loaded" },
        {
            trigger: ".o_cp_action_menus button",
            content: "Open the list's Actions (cog) menu",
            run: "click",
        },
        {
            trigger: ".dropdown-item:contains('Import from Esfera')",
            content: "Click 'Import from Esfera'",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='file']",
            content: "Import wizard loaded",
            run: async () => {
                const file = base64ToFile(XLSX_SUCCESS_B64, "esfera_success.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
                await inputFiles(".o_field_widget[name='file'] .o_input_file", [file]);
            },
        },
        {
            trigger: ".o_field_widget[name='file'] input.o_input:value(esfera_success.xlsx)",
            content: "File attached",
        },
        {
            trigger: ".modal footer button[name='action_import']",
            content: "Import students",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='result_html']:contains('Students created')",
            content: "The import succeeded - result summary shows a real created count",
        },
    ],
});
