/** @odoo-module **/

import { registry } from "@web/core/registry";
import { inputFiles } from "@web/../tests/utils";

// Doc screenshot of the title import preview (issue #635), driven by
// tests/test_docs_screenshots_academic_history.py (TestDocsScreenshotsTitles): its identifiers
// are the fixture students'.
const CSV = [
    "Identificador de l'alumne/a;Nom;Primer cognom;Segon cognom;Curs;Estat de la sol·licitud",
    "TESTDOC635001;Arnau;Puig;Casals;2024-2025;Registrada",
    "TESTDOC635002;Clara;Vidal;Font;2024-2025;Registrada",
    "TESTDOC635003;Biel;Roca;Serra;2024-2025;Alta",
    "TESTDOC635004;Núria;Pons;Mas;2024-2025;Sol·licitud anul·lada",
    "TESTDOC635099;Jana;Riera;Coll;2024-2025;Registrada",
].join("\n");

registry.category("web_tour.tours").add("ems_doc_shot_title_import", {
    test: true,
    steps: () => [
        {
            trigger: ".o_dialog .o_field_widget[name='file']",
            content: "Attach the list of graduates",
            run: async () => {
                const file = new File([CSV], "titols_2024-2025.csv", { type: "text/csv" });
                await inputFiles(".o_dialog .o_field_widget[name='file'] .o_input_file", [file]);
            },
        },
        {
            trigger: ".o_dialog .o_field_widget[name='file'] input.o_input:value(titols_2024-2025.csv)",
            content: "File attached",
        },
        {
            trigger: ".o_dialog footer button[name='action_preview']",
            content: "Preview",
            run: "click",
        },
        {
            trigger: ".o_dialog .o_field_widget[name='line_ids'] .o_data_row:nth-child(5)",
            content: "Every student of the file is listed with its result",
        },
    ],
});
