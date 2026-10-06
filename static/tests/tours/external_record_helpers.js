/** @odoo-module **/

// Shared by the tours of the "Add a previous record" wizard (issue #585): upload, into its
// certificate field, an invented academic record PDF the Python side serves through an xmlid.
// The file input itself is hidden behind the widget's Upload button, and a tour only triggers on
// visible elements: the step waits for the field and sets the input's files in run().
export function uploadCertificate(xmlid) {
    return {
        trigger: ".modal div[name='certificate_file']",
        content: "Upload the academic record PDF",
        async run() {
            const response = await fetch(`/web/content/${xmlid}`);
            const file = new File([await response.blob()], "certificate.pdf",
                                  { type: "application/pdf" });
            const transfer = new DataTransfer();
            transfer.items.add(file);
            const input = document.querySelector(
                ".modal div[name='certificate_file'] input[type='file']");
            input.files = transfer.files;
            input.dispatchEvent(new Event("change", { bubbles: true }));
        },
    };
}
