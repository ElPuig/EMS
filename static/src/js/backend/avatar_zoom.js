/** @odoo-module **/

import { Component } from "@odoo/owl";
import { usePopover } from "@web/core/popover/popover_hook";

// Delay before the enlarged photo opens on hover, so sweeping the mouse across a list of
// photos (e.g. on the way to a row's buttons) doesn't flash one popover per row.
const HOVER_DELAY_MS = 150;

export class AvatarZoom extends Component {
    static template = "ems.AvatarZoom";
    static props = {
        partnerId: Number,
        name: { type: String, optional: true },
        close: { type: Function, optional: true },
    };

    get imageUrl() {
        // image_512, not the thumbnail's image_128: the enlarged photo is shown at ~3x the
        // thumbnail's size, which image_128 can't fill sharply on HiDPI screens.
        return `/web/image/res.partner/${this.props.partnerId}/image_512`;
    }
}

/**
 * Enlarges a partner's photo on hover (or on click/tap, for touch screens without hover).
 * Rendered through Odoo's popover service, i.e. in the webclient's overlay container, so the
 * enlarged photo is never clipped by a scrolling parent or hidden under a sticky header.
 *
 * The enlarged photo sits next to the thumbnail, over the partner's name, so the name is repeated
 * as a caption under it.
 *
 * Usage: `this.avatarZoom = useAvatarZoom();` then, on the thumbnail `<img>`, passing the
 * partner as a `[id, display_name]` many2one pair (or false):
 * `t-on-mouseenter="(ev) => avatarZoom.onEnter(ev, partner)"`,
 * `t-on-mouseleave="avatarZoom.onLeave"`, `t-on-click="(ev) => avatarZoom.onClick(ev, partner)"`.
 */
export function useAvatarZoom() {
    const popover = usePopover(AvatarZoom, {
        position: "right-middle",
        arrow: false,
        animation: false,
        popoverClass: "ems-avatar-zoom-popover",
    });
    let timer = null;
    const cancel = () => {
        clearTimeout(timer);
        timer = null;
    };
    const open = (target, [partnerId, name]) => popover.open(target, { partnerId, name });
    return {
        onEnter(ev, partner) {
            cancel();
            if (!partner) {
                return;
            }
            const target = ev.currentTarget;
            timer = setTimeout(() => open(target, partner), HOVER_DELAY_MS);
        },
        onLeave() {
            cancel();
            popover.close();
        },
        onClick(ev, partner) {
            cancel();
            if (popover.isOpen) {
                popover.close();
            } else if (partner) {
                open(ev.currentTarget, partner);
            }
        },
    };
}
