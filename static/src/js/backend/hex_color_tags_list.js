/** @odoo-module **/

import { TagsList } from "@web/core/tags_list/tags_list";

// Same behaviour as the core TagsList, only the template differs: it paints each tag with
// its own inline bgColor/textColor instead of one of the fixed "o_tag_color_0..11" classes,
// since ems.role colors are now freely-picked hex values, not a predetermined palette index.
export class HexColorTagsList extends TagsList {
    static template = "ems.HexColorTagsList";
}
