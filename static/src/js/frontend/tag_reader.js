/** @odoo-module **/

import { onWillDestroy, useExternalListener } from "@odoo/owl";

// The reader, as Odoo's own barcode service (the one the clock-in kiosk uses) takes it: keys
// that come close together are a tag, keys that come apart are somebody typing and are dropped.
const MAX_TIME_BETWEEN_KEYS_MS = 150;
const MIN_CODE_LENGTH = 3;

/**
 * Read NFC tags on a public page, like the clock-in kiosk: there is no box to type in. An NFC
 * reader is a USB keyboard, it types the tag's UID and ends with Enter; a listener on the whole page
 * collects the keys and takes them for a tag only if they came fast, as Odoo's barcode service does
 * (150 ms at most between keys), so somebody typing a code by hand reads nothing. The service itself
 * is not used: it needs the web client's environment, and these pages are public components.
 * Keys typed into a box (the testing aid some pages show outside production) are left to it.
 *
 * `onTag(code)` is called with every tag read.
 */
export function useTagReader(onTag) {
    let keys = "";
    let keyTimeout = null;

    // Enter or Tab (or the reader going quiet for MAX_TIME_BETWEEN_KEYS_MS) ends the buffer, and a
    // buffer of at least MIN_CODE_LENGTH keys is a tag. A person typing is too slow for that: the
    // buffer is emptied after every key and never reaches three.
    const checkKeys = (ev) => {
        const code = keys.replace(/Alt|Shift|Control/g, "");
        keys = "";
        if (code.length >= MIN_CODE_LENGTH) {
            ev?.preventDefault();
            onTag(code);
        }
    };

    useExternalListener(document, "keydown", (ev) => {
        if (!ev.key) {
            return;
        }
        // Only printable keys and the two that end a code count (Shift, arrows, F keys... do not).
        const isEnd = ev.key === "Enter" || ev.key === "Tab";
        const isSpecial = !["Control", "Alt"].includes(ev.key) && (ev.key.length > 1 || ev.metaKey);
        if (isSpecial && !isEnd) {
            return;
        }
        if (ev.target.matches?.("input, textarea, [contenteditable='true']")) {
            return;
        }
        clearTimeout(keyTimeout);
        if (isEnd) {
            checkKeys(ev);
        } else {
            keys += ev.key;
            keyTimeout = setTimeout(() => checkKeys(), MAX_TIME_BETWEEN_KEYS_MS);
        }
    });
    onWillDestroy(() => clearTimeout(keyTimeout));
}
