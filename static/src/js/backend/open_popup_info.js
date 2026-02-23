/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class OpenRecordPopupField extends Component {
    static template = "ems.PopupInfo";
    static props = { ...standardFieldProps };

    setup() {
        this.action = useService("action");
    }

    get tags() {
        const record = this.props.record.data;
        const textValue = String(record[this.props.name]) || ""; 
        
        const textParts = textValue.split(';').map(t => t.trim()).filter(Boolean);

        // 2. Obtenemos la lista de IDs del One2many
        const options = this.props.options || {};
        const relatedField = options.related_id_field;
        const fieldData = record[relatedField];

        let ids = [];
        if (fieldData && fieldData.currentIds) {
            ids = fieldData.currentIds; 
        } else if (Array.isArray(fieldData)) {
            ids = fieldData;
        }

        // 3. Mapeamos: Texto[0] -> ID[0], Texto[1] -> ID[1]
        return textParts.map((text, index) => {
            return {
                id: index,         
                text: text,        
                resId: ids[index], 
                isClickable: !!ids[index]             };
        });
    }

    async openTag(resId) {
        if (!resId) return;

        const options = this.props.options || {};
        const resModel = options.res_model;

        await this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: resModel,
            res_id: resId, 
            views: [[false, "form"]],
            target: 'new',
            name: options.title || 'Información',
        });
    }
}

export const openPopupInfo = {
    component: OpenRecordPopupField,
    supportedTypes: ["char", "text"],
    extractProps: ({ attrs, options }) => {
        return { options: options };
    },
};


registry.category("fields").add("open_popup_info", openPopupInfo);