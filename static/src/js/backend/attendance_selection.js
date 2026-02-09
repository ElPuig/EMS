/** @odoo-module */

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl"; 
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const STATUS_OPTIONS = [
    { value: "a_attended", label: "Attended", icon: "fa-check", color: "success" },
    { value: "a_delayed", label: "Delayed", icon: "fa-clock-o", color: "info" },
    { value: "m_miss", label: "Miss", icon: "fa-times", color: "danger" },
    { value: "m_justified", label: "Justified", icon: "fa-file-text-o", color: "warning" },
    { value: "a_issue", label: "Issue", icon: "fa-exclamation-triangle", color: "secondary" }
];

export class AttendaceSelection extends Component {
    static template = "ems.AttendanceSelection";
    

    static props = {
        ...standardFieldProps,
    };

    get options() {
        return STATUS_OPTIONS;
    }

    getButtonClass(option) {
        const currentValue = this.props.record.data[this.props.name];
        const isSelected = currentValue === option.value;
        
        if (isSelected) {
            return `btn-${option.color} shadow-sm border border-dark`;
        } else {
            return `btn-outline-${option.color} opacity-75`;
        }
    }

    async updateStatus(value, ev) {
        if (ev) {
            ev.stopPropagation();
        }

        try {
            await this.props.record.update({ [this.props.name]: value });
            await this.props.record.save();
        } catch (error) {
            console.error("Error actualizando asistencia:", error);
        }
    }
}

export const attendaceSelection = {
    component: AttendaceSelection,
    supportedTypes: ["selection", "char"],
};

registry.category("fields").add("attendance_selection", attendaceSelection);