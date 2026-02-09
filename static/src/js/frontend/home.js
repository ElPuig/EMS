/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

export class StudentCard extends Component {
    static template = "ems.StudentCard";

    setup() {
        this.state = useState({
            student: null,
            loading: true,
            isEditing: false,
            saving: false
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        try {
            const data = await rpc("/ems/get_student_info");
            this.state.student = data;
        } catch (e) {
            console.error("Error cargando datos:", e);
        } finally {
            this.state.loading = false;
        }
    }

    toggleEdit() {
        this.state.isEditing = !this.state.isEditing;
    }

    async saveCarPlate() {
        if (!this.state.student) return;

        this.state.saving = true;
        try {
            await rpc("/ems/update_student_car_plate", {
                car_plate: this.state.student.car_plate
            });

            this.state.isEditing = false;
        } catch (e) {
            console.error("❌ Error al guardar:", e);
            alert("Hubo un error al guardar los cambios.");
        } finally {
            this.state.saving = false;
        }
    }

    async printAttendance() {
        try {
            const res = await rpc(
                "/portal/wizard/submit",
                {
                    student_id: this.state.student.id,
                    level_id: this.state.student.level_id,
                    study_id: this.state.student.study_id,
                    group_id: this.state.student.group_id
                }
            );
    
            if (res.status === 'ok' && res.url) {
                window.location.href = res.url; 
            } else {
                this.state.result = res.message || "Error desconocido";
            }
        } catch (err) {
            console.error(err);
            this.state.result = "Error al enviar el wizard";
        }
    }    
}

registry.category("public_components").add("ems.StudentCard", StudentCard);