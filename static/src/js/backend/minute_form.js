/** @odoo-module **/

import { onMounted, onWillUnmount, useExternalListener } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { EmsCanEditFormController } from "./can_edit_form";

// How often the form looks whether there is something to save, how long the writer must have
// been still for it to save (so it never cuts in between two keystrokes), and the least time
// between two saves.
const TICK = 4000;
const IDLE = 2500;
const BETWEEN_SAVES = 12000;

// What the writer is typing in, as something that survives the form being redrawn: its position
// among the form's text boxes (the same after a save, which adds or removes none) and the caret's
// offset in its text.
const TEXT_BOXES = ".odoo-editor-editable, input:not([type='hidden']), textarea";

function rememberCaret(root) {
    const active = document.activeElement;
    const box = active && active.closest && active.closest(TEXT_BOXES);
    if (!box || !root.contains(box)) {
        return null;
    }
    const index = [...root.querySelectorAll(TEXT_BOXES)].indexOf(box);
    if (!box.isContentEditable) {
        return { index, offset: box.selectionEnd };
    }
    const selection = document.getSelection();
    if (!selection.rangeCount) {
        return { index, offset: null };
    }
    const before = selection.getRangeAt(0).cloneRange();
    before.selectNodeContents(box);
    const range = selection.getRangeAt(0);
    before.setEnd(range.endContainer, range.endOffset);
    return { index, offset: before.toString().length };
}

function restoreCaret(root, caret) {
    const box = root.querySelectorAll(TEXT_BOXES)[caret.index];
    if (!box || box.contains(document.activeElement)) {
        return;
    }
    box.focus();
    if (!box.isContentEditable) {
        const offset = caret.offset ?? box.value.length;
        box.setSelectionRange(offset, offset);
        return;
    }
    // The text node holding the offset, or the end of the text when it no longer has that many characters.
    const walker = document.createTreeWalker(box, NodeFilter.SHOW_TEXT);
    let left = caret.offset ?? Infinity;
    let node = walker.nextNode();
    let last = null;
    while (node && left > node.length) {
        left -= node.length;
        last = node;
        node = walker.nextNode();
    }
    const range = document.createRange();
    if (node) {
        range.setStart(node, left);
    } else if (last) {
        range.setStart(last, last.length);
    } else {
        range.selectNodeContents(box);
        range.collapse(false);
    }
    range.collapse(true);
    const selection = document.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
}

/** Whether the changes add lines to a one2many: those need the save to reload, for their ids. */
function addsLines(changes) {
    return Object.values(changes).some(
        (value) => Array.isArray(value) && value.some((command) => Array.isArray(command) && command[0] === 0)
    );
}

// A minute is written live, during the meeting, often on a laptop on its battery. Odoo saves a
// form when the user leaves it, not while they stay on it writing - an hour of meeting would
// hang on one click. This form saves by itself, in the pauses of whoever is writing.
export class EmsMinuteFormController extends EmsCanEditFormController {
    setup() {
        super.setup();
        this.lastInput = 0;
        this.lastAutosave = 0;
        this.autosaving = false;
        const noteInput = () => {
            this.lastInput = Date.now();
        };
        useExternalListener(window, "keydown", noteInput, { capture: true });
        useExternalListener(window, "pointerdown", noteInput, { capture: true });
        let timer;
        onMounted(() => {
            timer = browser.setInterval(() => this.autosave(), TICK);
        });
        onWillUnmount(() => browser.clearInterval(timer));
    }

    async autosave() {
        const record = this.model.root;
        const now = Date.now();
        // Not a minute that was never saved (saving it issues its code: that is the writer's
        // call), not while a dialog is open, and not while the writer is at it.
        if (this.autosaving || record.isNew || !record.isInEdition || now - this.lastInput < IDLE || now - this.lastAutosave < BETWEEN_SAVES
                || document.querySelector(".modal.show, .o_dialog")) {
            return;
        }
        this.autosaving = true;
        try {
            // isDirty() also collects what is still only in an editor, so nothing typed is missed.
            if ((await record.isDirty()) && record._checkValidity({ silent: true })) {
                this.lastAutosave = Date.now();
                // Saving must not take the cursor out of the text being written (issue #755). When
                // only existing lines changed the form is not reloaded, so nothing is redrawn; new
                // lines need the reload for their ids, and the cursor is put back where it was.
                if (!addsLines(record._getChanges())) {
                    await record.save({ reload: false, onError: () => {} });
                } else {
                    const root = this.rootRef.el;
                    const caret = root && rememberCaret(root);
                    await record.save({ onError: () => {} });
                    if (caret) {
                        // After the redraw the save causes, which happens on the next frame.
                        await new Promise((resolve) => browser.requestAnimationFrame(() => browser.setTimeout(resolve)));
                        restoreCaret(root, caret);
                    }
                }
            }
        } catch {
            // A failed attempt is not the writer's problem to dismiss every few seconds: what they
            // wrote is still on screen, and the next pause tries again.
        } finally {
            this.autosaving = false;
        }
    }
}

registry.category("views").add("ems_minute_form", { ...formView, Controller: EmsMinuteFormController });
