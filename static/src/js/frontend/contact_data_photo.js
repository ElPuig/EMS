/** @odoo-module **/

import { loadBundle } from "@web/core/assets";
import publicWidget from "@web/legacy/js/public/public_widget";

// Portrait frame of the student's photo, as on an ID card.
const ASPECT_RATIO = 3 / 4;
// Size of the photo sent: plenty for class lists and grades, and a small upload.
const OUTPUT = { maxWidth: 900, maxHeight: 1200 };
// The zoom slider goes from the photo fitted in the frame (0) to this many times bigger (100).
const MAX_ZOOM = 5;
const TYPES = ["image/jpeg", "image/png"];

/**
 * The student's photo on /my/dades-contacte (issue #507 follow-up): the photo picked is shown in
 * Cropper.js (Odoo's own copy, html_editor.assets_image_cropper, loaded only when a photo is
 * picked) to move, zoom and rotate it within a portrait frame, with a live preview next to the
 * photo on file. On sending, the framed photo goes as a JPEG in the hidden s_photo_data input and
 * the file input is emptied, so the server gets only what the family saw - and validates it again
 * (ems.contact.data.request._ems_photo_from_upload). Without JavaScript the file input is sent as
 * is. Every word shown is in the QWeb template, so it is translated there.
 */
publicWidget.registry.EmsContactDataPhoto = publicWidget.Widget.extend({
    selector: ".o_ems_contact_data_photo",
    events: {
        "change input[name='s_photo']": "_onFileChange",
        "input .o_ems_photo_zoom": "_onZoomSlider",
        "click .o_ems_photo_zoom_in": "_onZoomIn",
        "click .o_ems_photo_zoom_out": "_onZoomOut",
        "click .o_ems_photo_rotate": "_onRotate",
        "click .o_ems_photo_discard": "_onDiscard",
    },

    start() {
        this.fileInput = this.el.querySelector("input[name='s_photo']");
        this.dataInput = this.el.querySelector("input[name='s_photo_data']");
        this.editor = this.el.querySelector(".o_ems_photo_editor");
        this.source = this.el.querySelector(".o_ems_photo_source");
        this.slider = this.el.querySelector(".o_ems_photo_zoom");
        this.newPhoto = this.el.querySelector(".o_ems_photo_new");
        this.preview = this.el.querySelector(".o_ems_photo_new_preview");
        this.discard = this.el.querySelector(".o_ems_photo_discard");
        this.typeError = this.el.querySelector(".o_ems_photo_type_error");
        this.savedPreview = this.preview.innerHTML;
        this.onSubmit = this._onSubmit.bind(this);
        this.el.closest("form").addEventListener("submit", this.onSubmit);
        return this._super(...arguments);
    },

    destroy() {
        this.el.closest("form")?.removeEventListener("submit", this.onSubmit);
        this._stopCropper();
        this._super(...arguments);
    },

    async _onFileChange() {
        const file = this.fileInput.files[0];
        this.typeError.classList.add("d-none");
        if (!file) {
            return;
        }
        if (!TYPES.includes(file.type)) {
            this.typeError.classList.remove("d-none");
            this.fileInput.value = "";
            return;
        }
        await loadBundle("html_editor.assets_image_cropper");
        this._stopCropper();
        this.objectUrl = URL.createObjectURL(file);
        this.source.src = this.objectUrl;
        this.editor.classList.remove("d-none");
        this.newPhoto.classList.remove("d-none");
        this.discard.classList.remove("d-none");
        this.cropper = new window.Cropper(this.source, {
            aspectRatio: ASPECT_RATIO,
            viewMode: 1,
            dragMode: "move",
            autoCropArea: 0.9,
            toggleDragModeOnDblclick: false,
            background: false,
            preview: this.preview,
            ready: () => {
                this.fitRatio = this.cropper.getImageData().width / this.cropper.getImageData().naturalWidth;
                this.slider.value = 0;
            },
            zoom: (ev) => {
                // Moved with the wheel or a pinch too: keep the slider where the photo is.
                if (this.fitRatio) {
                    const ratio = ev.detail.ratio / this.fitRatio;
                    if (ratio < 1 || ratio > MAX_ZOOM) {
                        ev.preventDefault();
                        return;
                    }
                    this.slider.value = ((ratio - 1) / (MAX_ZOOM - 1)) * 100;
                }
            },
        });
    },

    _onZoomSlider() {
        if (this.cropper && this.fitRatio) {
            const ratio = 1 + (this.slider.value / 100) * (MAX_ZOOM - 1);
            this.cropper.zoomTo(this.fitRatio * ratio);
        }
    },

    _onZoomIn() {
        this.cropper?.zoom(0.1);
    },

    _onZoomOut() {
        this.cropper?.zoom(-0.1);
    },

    _onRotate() {
        this.cropper?.rotate(90);
    },

    /** Back to the photo on file: nothing is sent, not even a photo sent before. */
    _onDiscard() {
        this._stopCropper();
        this.fileInput.value = "";
        this.dataInput.value = "";
        this.editor.classList.add("d-none");
        this.newPhoto.classList.add("d-none");
        this.discard.classList.add("d-none");
        this.el.querySelector(".o_ems_photo_pending")?.classList.add("d-none");
    },

    _onSubmit() {
        if (!this.cropper) {
            return;
        }
        const canvas = this.cropper.getCroppedCanvas({
            ...OUTPUT,
            fillColor: "#fff",
            imageSmoothingQuality: "high",
        });
        this.dataInput.value = canvas.toDataURL("image/jpeg", 0.9).split(",")[1];
        this.fileInput.value = "";
    },

    _stopCropper() {
        if (this.cropper) {
            this.cropper.destroy();
            this.cropper = null;
            this.fitRatio = null;
            this.preview.innerHTML = this.savedPreview;
        }
        if (this.objectUrl) {
            URL.revokeObjectURL(this.objectUrl);
            this.objectUrl = null;
        }
    },
});

export default publicWidget.registry.EmsContactDataPhoto;
