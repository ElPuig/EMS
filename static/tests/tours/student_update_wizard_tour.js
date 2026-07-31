/** @odoo-module **/

import { registry } from "@web/core/registry";
import { inputFiles } from "@web/../tests/utils";

function csvContent() {
    return ["IDALU,Nom", "9999999999,Updated Tour Name"].join("\n");
}

// ems.student_update_wizard (EMS: Update students from CSV): a two-step wizard (upload ->
// map CSV columns via dynamically-created ems.csv_column records -> apply) had zero browser
// coverage. This tour drives the whole flow: upload, "Load columns", pick the IDALU and Nom
// columns via their many2one autocompletes, "Update students", verifying the underlying
// student's name actually changed afterward.
registry.category("web_tour.tours").add("ems_student_update_wizard_apply", {
    test: true,
    url: "/odoo/action-ems.action_student_update_wizard",
    steps: () => [
        {
            trigger: ".o_form_view .o_field_widget[name='file']",
            content: "Update wizard loaded",
            run: async () => {
                const file = new File([csvContent()], "update.csv", { type: "text/csv" });
                await inputFiles(".o_field_widget[name='file'] .o_input_file", [file]);
            },
        },
        {
            trigger: ".o_field_widget[name='file'] input.o_input:value(update.csv)",
            content: "File attached",
        },
        {
            trigger: ".modal footer button[name='action_load_columns']",
            content: "Load columns",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='col_student_id'] input",
            content: "Map the IDALU column",
            run: "edit IDALU",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('IDALU')",
            content: "Select it",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='col_name'] input",
            content: "Map the Nom (name) column",
            run: "edit Nom",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Nom')",
            content: "Select it",
            run: "click",
        },
        {
            trigger: ".modal footer button[name='action_update']",
            content: "Update students",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='result_html']",
            content: "Update result rendered",
        },
    ],
});
