/** @odoo-module **/
import { registry } from "@web/core/registry";
import { BinaryField, binaryField } from "@web/views/fields/binary/binary_field";
import { onMounted } from "@odoo/owl";

class AutoDownloadBinaryField extends BinaryField {
    setup() {
        super.setup();
        onMounted(() => {
            if (this.props.record.data[this.props.name]) {
                this.onFileDownload();
            }
        });
    }
}

registry.category("fields").add("auto_download_binary", {
    ...binaryField,
    component: AutoDownloadBinaryField,
});
