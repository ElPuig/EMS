/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

/**
 * Issue #844: on the student walkout portal pages (/my/vagues), right after a student votes or says
 * whether they join, or a family ratifies, the page pops up what was saved
 * (ems.portal_student_walkout_saved_modal): without it, students thought nothing had happened.
 * Every word shown is in the QWeb template, so it is translated there; this only opens it.
 */
publicWidget.registry.EmsWalkoutSavedModal = publicWidget.Widget.extend({
    selector: ".o_ems_walkout_saved_modal",

    start() {
        window.Modal.getOrCreateInstance(this.el).show();
        // Reloading the page must not pop it up again: drop "saved" from the address.
        const url = new URL(window.location.href);
        url.searchParams.delete("saved");
        window.history.replaceState(null, "", url);
        return this._super(...arguments);
    },
});
