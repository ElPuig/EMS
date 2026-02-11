/** @odoo-module */

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl"; 
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const STATUS_OPTIONS = [
    { value: "a_attended", label: "Attended", icon: "fa-check", color: "success" },
    { value: "a_delayed", label: "Delayed", icon: "fa-clock-o", color: "warning" },
    { value: "m_miss", label: "Miss", icon: "fa-times", color: "danger" },
    { value: "m_justified", label: "Justified Miss", icon: "fa-file-text-o", color: "info" },
    { value: "a_issue", label: "Issue", icon: "fa-exclamation-triangle", color: "dark" }
];

export class AttendanceSelection extends Component {
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
        
        let baseClass = "btn btn-sm shadow-none justify-content-center flex-grow-1 flex-md-grow-0 "; 
        
        if (isSelected) {
            return baseClass + `bg-${option.color} text-white border border-${option.color} fw-bold`;
        } else {
            return baseClass + `bg-white text-${option.color} border border-${option.color}`;
        }
    }

    async updateStatus(value, ev) {
        ev?.stopPropagation(); 

        if (this.props.record.data[this.props.name] === value) return;

        this.props.record.update({ [this.props.name]: value });
    }
}

export const attendanceSelection = {
    component: AttendanceSelection,
    supportedTypes: ["selection", "char"],
};

registry.category("fields").add("attendance_selection", attendanceSelection);