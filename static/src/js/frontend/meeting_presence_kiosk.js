/** @odoo-module **/

import {
    Component,
    onMounted,
    onPatched,
    onWillDestroy,
    useExternalListener,
    useRef,
    useState,
} from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";

// How long the card of the person who just passed their tag stays on screen.
const CARD_MS = 3500;
// The lists show every name without scrolling, however many there are: font size and number of
// columns are worked out from the room the list has (see fitNames). These are the limits.
const FONT_MAX = 36; // px: a handful of names are shown big
const FONT_MIN = 9; // px: below this the list scrolls instead, a last resort for an enormous meeting
const MAX_COLUMNS = 6;
const ROW_FACTOR = 1.3; // a row's height in font sizes: line height plus its padding
const COLUMN_GAP = 16; // px

// The reader, as Odoo's own barcode service (the one the clock-in kiosk uses) takes it: keys
// that come close together are a tag, keys that come apart are somebody typing and are dropped.
const MAX_TIME_BETWEEN_KEYS_MS = 150;
const MIN_CODE_LENGTH = 3;

// How often the page asks the server whether the session takes tags now: it can start, end, close
// or reopen while the page is up, and nobody should have to reload the laptop at the door.
const POLL_MS = 5000;

// Which card each answer of the server shows: 'tone' is the colour, 'showName' whether somebody
// matched (an unknown tag has nobody to show). Every word comes from props.labels, already
// translated by the server: the page is anonymous, so the web client's translation loading does
// not reach it (see views/minutes_agreements/presence/kiosk.xml).
const CARDS = {
    ok: { tone: "success", showName: true },
    already: { tone: "info", showName: true },
    not_convened: { tone: "warning", showName: true },
    unknown: { tone: "danger", showName: false },
    error: { tone: "danger", showName: false },
};

/**
 * The kiosk of a meeting attendance (issue #521), mounted by the public component service on
 * /ems/presence/<token>. It works like the clock-in kiosk: there is no box to type in. An NFC
 * reader is a USB keyboard, it types the tag's UID and ends with Enter; a listener on the whole
 * page collects the keys and takes them for a tag only if they came fast, as Odoo's barcode service
 * does (150 ms at most between keys), so somebody typing a code by hand registers nothing.
 * The one exception is a box to type a code in, shown only outside production
 * (props.showCodeBox), for trying the kiosk out where there is no reader.
 */
export class MeetingPresenceKiosk extends Component {
    static template = "ems.MeetingPresenceKiosk";
    static props = {
        token: String,
        name: String,
        windowLabel: String,
        showCodeBox: Boolean,
        status: String,
        labels: Object,
        present_count: Number,
        pending_count: Number,
        convened: Array,
        attendees: Array,
    };

    setup() {
        this.input = useRef("barcodeInput");
        this.convenedNames = useRef("convenedNames");
        this.attendeeNames = useRef("attendeeNames");
        this.state = useState({
            // 'open', or the reason the session takes no tags: 'not_open' / 'closed'.
            status: this.props.status,
            presentCount: this.props.present_count,
            pendingCount: this.props.pending_count,
            // Who is still to come and who is in: names only, kept up to date by every answer of
            // the server (scans and polls).
            convened: this.props.convened,
            attendees: this.props.attendees,
            card: null,
        });
        // Scans are handled one after another: two people passing their tag one right after the
        // other must both be registered, and the second card must not race the first.
        this.queue = Promise.resolve();
        this.hideTimeout = null;
        this.keyTimeout = null;
        this.keys = "";
        onMounted(() => {
            this.fitLists();
            // The font the names are measured with may not be there yet.
            document.fonts?.ready.then(() => this.fitLists());
        });
        onPatched(() => this.fitLists());
        useExternalListener(window, "resize", () => this.fitLists());
        useExternalListener(document, "visibilitychange", () => this.refreshStatus());
        this.pollTimer = setInterval(() => this.refreshStatus(), POLL_MS);
        onWillDestroy(() => {
            clearInterval(this.pollTimer);
            clearTimeout(this.hideTimeout);
            clearTimeout(this.keyTimeout);
        });
        useExternalListener(document, "keydown", (ev) => this.onKeydown(ev));
    }

    get labels() {
        return this.props.labels;
    }

    /**
     * The reader: the same rules as Odoo's barcode service. Keys pile up in a buffer; Enter or Tab
     * (or the reader going quiet for MAX_TIME_BETWEEN_KEYS_MS) ends it, and a buffer of at least
     * MIN_CODE_LENGTH keys is a tag. A person typing is too slow for that: the buffer is emptied
     * after every key and never reaches three.
     */
    onKeydown(ev) {
        if (!ev.key) {
            return;
        }
        // Only printable keys and the two that end a code count (Shift, arrows, F keys... do not).
        const isEnd = ev.key === "Enter" || ev.key === "Tab";
        const isSpecial = !["Control", "Alt"].includes(ev.key) && (ev.key.length > 1 || ev.metaKey);
        if (isSpecial && !isEnd) {
            return;
        }
        // Whoever types in the code box is not a reader: that box has its own submit.
        if (ev.target.matches?.("input, textarea, [contenteditable='true']")) {
            return;
        }
        clearTimeout(this.keyTimeout);
        if (isEnd) {
            this.checkKeys(ev);
        } else {
            this.keys += ev.key;
            this.keyTimeout = setTimeout(() => this.checkKeys(), MAX_TIME_BETWEEN_KEYS_MS);
        }
    }

    checkKeys(ev) {
        const code = this.keys.replace(/Alt|Shift|Control/g, "");
        this.keys = "";
        if (code.length >= MIN_CODE_LENGTH) {
            ev?.preventDefault();
            this.register(code);
        }
    }

    /** The code box (outside production only): typing there and pressing Enter registers a tag. */
    onSubmit(ev) {
        ev.preventDefault();
        const input = this.input.el;
        const code = input.value.trim();
        input.value = "";
        if (code) {
            this.register(code);
        }
    }

    register(code) {
        this.queue = this.queue.then(() => this.scan(code));
    }

    /**
     * Give each list the biggest font that lets every name show, laid out in as many columns as
     * that takes: a few names get one big column, a staff meeting's hundred get several small ones
     * and nobody has to scroll to find themselves. Measured, not guessed: the widest row of the
     * list decides how many columns its width holds.
     */
    fitLists() {
        this.fitNames(this.convenedNames.el, this.state.convened.map((person) => person.name));
        this.fitNames(
            this.attendeeNames.el,
            this.state.attendees.map((person) =>
                [person.name, person.not_convened ? this.labels.not_convened_note : "", person.time].join(" ")
            )
        );
    }

    fitNames(el, texts) {
        if (!el || !texts.length || !el.clientWidth || !el.clientHeight) {
            return;
        }
        this.measure ||= document.createElement("canvas").getContext("2d");
        this.measure.font = `600 100px ${getComputedStyle(el).fontFamily}`;
        // Width of the widest row per pixel of font size, with a margin for the rounding.
        const widest =
            (Math.max(...texts.map((text) => this.measure.measureText(text).width)) / 100) * 1.06;
        let best = { font: 0, columns: 1 };
        for (let columns = 1; columns <= Math.min(MAX_COLUMNS, texts.length); columns++) {
            const rows = Math.ceil(texts.length / columns);
            const byHeight = el.clientHeight / (rows * ROW_FACTOR);
            const byWidth = (el.clientWidth - COLUMN_GAP * (columns - 1)) / columns / widest;
            const font = Math.min(byHeight, byWidth, FONT_MAX);
            if (font > best.font + 0.01) {
                best = { font, columns };
            }
        }
        el.style.setProperty("--ems-font", `${Math.max(best.font, FONT_MIN)}px`);
        el.style.setProperty("--ems-columns", best.columns);
        el.style.setProperty("--ems-rows", Math.ceil(texts.length / best.columns));
        el.classList.toggle("o_ems_presence_names_scroll", best.font < FONT_MIN);
        el.dataset.fitted = "1";
    }

    async refreshStatus() {
        if (document.hidden) {
            return; // Nobody is looking at this tab: it asks again as soon as they do.
        }
        let result;
        try {
            result = await rpc(`/ems/presence/${this.props.token}/status`);
        } catch {
            return; // Offline for a moment: the next poll tells.
        }
        if (result.status !== "invalid") {
            this.applyServerState(result);
        }
    }

    applyServerState(result) {
        if (result.status) {
            this.state.status = result.status;
        }
        if (result.present_count !== undefined) {
            this.state.presentCount = result.present_count;
            this.state.pendingCount = result.pending_count;
            this.state.convened = result.convened;
            this.state.attendees = result.attendees;
        }
    }

    async scan(barcode) {
        let result;
        try {
            result = await rpc(`/ems/presence/${this.props.token}/scan`, { barcode });
        } catch {
            result = { status: "error" };
        }
        if (result.status === "not_open" || result.status === "closed") {
            // Somebody changed the session under the kiosk: it stops taking tags.
            this.applyServerState(result);
            return;
        }
        this.applyServerState({ ...result, status: undefined });
        this.showCard(result);
    }

    showCard(result) {
        const card = CARDS[result.status] || CARDS.error;
        this.state.card = {
            tone: card.tone,
            title: card.showName ? result.employee_name : this.labels[result.status],
            subtitle: card.showName ? this.labels[result.status] : "",
            avatar: card.showName ? result.employee_avatar : false,
        };
        clearTimeout(this.hideTimeout);
        this.hideTimeout = setTimeout(() => {
            this.state.card = null;
        }, CARD_MS);
    }

    get isOpen() {
        return this.state.status === "open";
    }

    get closedLabel() {
        return this.labels[this.state.status];
    }
}

registry.category("public_components").add("ems.meeting_presence_kiosk", MeetingPresenceKiosk);
