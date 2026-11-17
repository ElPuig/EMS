/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FileViewer } from "@web/core/file_viewer/file_viewer";

// Odoo's file viewer for a file marked 'emsViewOnly' (ems_attachments on a confidential record):
// no Download or Print buttons, and the PDF reader's own download, print and open buttons are
// hidden too. Only what the browser shows can be hidden: a screenshot is still possible, and the
// server refuses the download whatever the buttons (models/erasmus/binary.py).
const PDF_HIDDEN = "#downloadButton, #secondaryDownload, #printButton, #secondaryPrint, #openFile, #secondaryOpenFile, #viewBookmark";

patch(FileViewer.prototype, {
    emsOnPdfLoad(ev) {
        if (!this.state.file.emsViewOnly) {
            return;
        }
        const doc = ev.target.contentDocument;
        const style = doc.createElement("style");
        style.textContent = `${PDF_HIDDEN} { display: none !important; }`;
        doc.head.appendChild(style);
    },
});
