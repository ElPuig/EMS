/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #845 - the files of an application are viewed in Odoo's file viewer; a confidential
// document's file offers no download, neither on its card nor in the viewer. Records seeded by
// tests/test_erasmus_file_viewer_tour.py. Issue #859: a document handed in as a link opens in a new
// tab, with no download.

const LINES = ".o_form_view .o_field_widget[name='document_ids']";

registry.category("web_tour.tours").add("ems_erasmus_file_viewer", {
    test: true,
    url: "/odoo/action-ems.action_erasmus_application",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row td[name='partner_id']:contains('Erasmus Test Student')",
            content: "Open the application",
            run: "click",
        },
        {
            trigger: `${LINES} .o_data_row:contains('Europass CV') .o_ems_attachment_download`,
            content: "A normal document's file card offers the download",
        },
        {
            trigger: `${LINES} .o_data_row:contains('Europass CV') .o_ems_attachment_preview`,
            content: "Preview it",
            run: "click",
        },
        {
            trigger: ".o-FileViewer .o-FileViewer-download",
            content: "Its viewer offers the download",
        },
        {
            trigger: ".o-FileViewer",
            content: "Close the viewer",
            run: "press Escape",
        },
        {
            trigger: `${LINES} .o_data_row:contains('Fewer opportunities') .o_ems_attachment_preview`,
            content: "The confidential document's file card has the eye",
            run: "click",
        },
        {
            trigger: ".o-FileViewer:not(:has(.o-FileViewer-download)):not(:has(.fa-print))",
            content: "Its viewer has neither Download nor Print",
        },
        {
            trigger: ".o-FileViewer",
            content: "Close the viewer",
            run: "press Escape",
        },
        {
            trigger: `${LINES} .o_data_row:contains('Fewer opportunities'):not(:has(.o_ems_attachment_download))`,
            content: "The confidential document's file card has no download",
        },
        {
            trigger: `${LINES} .o_data_row:contains('Presentation video') .o_ems_attachment_link[target='_blank'][href='https://example.com/video']`,
            content: "A link opens in a new tab",
        },
        {
            trigger: `${LINES} .o_data_row:contains('Presentation video'):not(:has(.o_ems_attachment_download, .o_ems_attachment_preview))`,
            content: "A link has neither download nor preview",
        },
    ],
});
