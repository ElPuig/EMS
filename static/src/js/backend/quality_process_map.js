/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// Quality > Process map: the centre keeps its process map as a Google document, so this screen
// only embeds its published copy (the address is a company setting). The map is edited in Drive
// and the published copy follows on its own - there is nothing to keep in sync from EMS.
export class QualityProcessMap extends Component {
    static template = "ems.QualityProcessMap";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({ url: false });
        onWillStart(async () => {
            this.state.url = await this.orm.call("ems.quality.process", "get_process_map_url", []);
        });
    }
}

registry.category("actions").add("ems_quality_process_map", QualityProcessMap);
