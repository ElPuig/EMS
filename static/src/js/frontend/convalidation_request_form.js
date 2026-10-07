/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

/**
 * The portal's new convalidation request form (/my/convalidaciones, issue #579): "Where did you
 * pass the studies?" is only asked for prior studies, and the supporting documents are required
 * unless the studies were passed at this centre - the same rule the server enforces
 * (ems.convalidation._ems_documents_required) whatever the browser sends. Every word shown is in
 * the QWeb template, so it is translated there; this only shows, hides and marks as required,
 * including which documents to attach for the chosen grounds.
 */
publicWidget.registry.EmsConvalidationRequestForm = publicWidget.Widget.extend({
    selector: ".o_ems_convalidation_new form",
    events: {
        "change select[name='basis']": "_update",
        "change select[name='prior_studies_origin']": "_update",
    },

    start() {
        this.basis = this.el.querySelector("select[name='basis']");
        this.origin = this.el.querySelector("select[name='prior_studies_origin']");
        this.documents = this.el.querySelector("input[name='documents']");
        this._update();
        return this._super(...arguments);
    },

    _update() {
        const priorStudies = this.basis.value === "prior_studies";
        this.el.querySelector(".o_ems_convalidation_origin").classList.toggle("d-none", !priorStudies);
        this.origin.required = priorStudies;
        const required = !(priorStudies && this.origin.value === "centre");
        this.documents.required = required;
        this.el.querySelector(".o_ems_convalidation_documents_required").classList.toggle("d-none", !required);
        this.el.querySelector(".o_ems_convalidation_documents_optional").classList.toggle("d-none", required);
        // Which documents to attach: only the guidance for these grounds (and origin) is shown.
        for (const guidance of this.el.querySelectorAll(".o_ems_convalidation_guidance")) {
            const matches = guidance.dataset.basis === this.basis.value
                && (guidance.dataset.origin === undefined || guidance.dataset.origin === this.origin.value);
            guidance.classList.toggle("d-none", !matches);
        }
    },
});
