/** @odoo-module **/

import { Component, onWillDestroy, useRef, useState } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { useTagReader } from "@ems/js/frontend/tag_reader";

// How long the meetings of whoever passed their tag stay on screen when nobody picks one.
const RESULT_MS = 30000;

/**
 * The meetings page (issue #526), mounted by the public component service on /ems/meetings: the
 * fixed address the computers with a reader keep open. Passing a tag lists the meetings its owner
 * can open today, each a link to its kiosk (which then leads back here); nobody picking one clears
 * the list. Tags are read like on the kiosk (see useTagReader), and every word comes from
 * props.labels, already translated by the server.
 */
export class MeetingPresenceHub extends Component {
    static template = "ems.MeetingPresenceHub";
    static props = {
        labels: Object,
        showCodeBox: Boolean,
    };

    setup() {
        this.input = useRef("barcodeInput");
        // status: '' waiting for a tag, 'ok', 'none' (nothing to open today), 'unknown' or 'error'.
        this.state = useState({ status: "", employeeName: "", meetings: [] });
        this.resetTimeout = null;
        onWillDestroy(() => clearTimeout(this.resetTimeout));
        useTagReader((code) => this.scan(code));
    }

    get labels() {
        return this.props.labels;
    }

    /** The code box (outside production only): typing there and pressing Enter reads a tag. */
    onSubmit(ev) {
        ev.preventDefault();
        const code = this.input.el.value.trim();
        this.input.el.value = "";
        if (code) {
            this.scan(code);
        }
    }

    async scan(barcode) {
        let result;
        try {
            result = await rpc("/ems/meetings/scan", { barcode });
        } catch {
            result = { status: "error" };
        }
        Object.assign(this.state, {
            status: result.status,
            employeeName: result.employee_name || "",
            meetings: result.meetings || [],
        });
        clearTimeout(this.resetTimeout);
        this.resetTimeout = setTimeout(() => {
            Object.assign(this.state, { status: "", employeeName: "", meetings: [] });
        }, RESULT_MS);
    }
}

registry.category("public_components").add("ems.meeting_presence_hub", MeetingPresenceHub);
