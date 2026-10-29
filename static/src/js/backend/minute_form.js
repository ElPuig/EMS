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
                await record.save({ onError: () => {} });
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
