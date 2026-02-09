/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

export class AttendanceKiosk extends Component {
    static template = "ems.AttendanceKiosk";

    setup() {
        this.state = useState({
            view: 'list', 
            sessions: [],      
            pastSessions: [], 
            showPast: false,   
            students: [],
            currentSessionName: '',
            date: '',
            startTime: 0
        });

        onWillStart(async () => {
            await this.loadSessions();
        });
    }

    async loadSessions() {
        try {
            const data = await rpc("/ems/get_my_sessions");
            this.state.sessions = data;
        } catch (e) {
            console.error(e);
        } 
    }

    async loadPastSessions() {
        try {
            const data = await rpc("/ems/get_past_sessions");
            this.state.pastSessions = data;
        } catch (e) {
            console.error(e);
        } 
    }

    async toggleHistory() {
        this.state.showPast = !this.state.showPast;
        if (this.state.showPast && this.state.pastSessions.length === 0) {
            await this.loadPastSessions();
        }
    }

    async openSession(sessionId) {
        try {
            const data = await rpc("/ems/get_session_students", { session_id: sessionId });
            
            this.state.students = data.students;

            this.state.currentSessionName = data.session_name;
            this.state.date = data.date;
            this.state.startTime = data.start_time;
            this.state.view = 'kiosk';
        } catch (e) {
            console.error(e);
        } 
    }

    goBack() {
        this.state.view = 'list';
        this.state.students = [];
    }

    setStatus(student, newStatus) {
        student.status = newStatus;
    }

    async signAttendance() {
        const changes = this.state.students.map(s => ({
            line_id: s.line_id,
            status: s.status
        }));

        try {
            await rpc("/ems/submit_attendance_batch", { changes: changes });
            
            alert("Asistencia guardada correctamente.");

        } catch (e) {
            console.error("Error al firmar", e);
            alert("Error al guardar. Comprueba tu conexión.");
        }
    }
}

registry.category("public_components").add("ems.AttendanceKiosk", AttendanceKiosk);