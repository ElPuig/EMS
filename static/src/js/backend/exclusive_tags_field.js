/** @odoo-module **/

import { useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { TagsList } from "@web/core/tags_list/tags_list";
import { Many2ManyTagsField, many2ManyTagsField } from "@web/views/fields/many2many_tags/many2many_tags_field";

// The tag being dragged, kept here rather than read back from the DataTransfer: browsers only
// expose its data on drop, and dragover has to know already whether to accept it.
let draggedTag = null;

export class DraggableTagsList extends TagsList {
    static template = "ems.DraggableTagsList";
}

/**
 * Many2many tags that exclude those of a sibling field of the same form (attendees and absentees
 * of a minute): adding somebody to one removes them from the other, and a tag can be dragged
 * from one to the other.
 */
export class ExclusiveTagsField extends Many2ManyTagsField {
    static template = "ems.ExclusiveTagsField";
    static components = { ...Many2ManyTagsField.components, TagsList: DraggableTagsList };
    static props = { ...Many2ManyTagsField.props, exclusiveWith: String };

    setup() {
        super.setup();
        this.dropState = useState({ over: false });
        const update = this.update;
        this.update = async (recordlist) => {
            await update(recordlist);
            await this.releaseFromSibling((recordlist || []).map((rec) => rec.id));
        };
    }

    get siblingList() {
        return this.props.record.data[this.props.exclusiveWith];
    }

    async releaseFromSibling(resIds) {
        const held = this.siblingList.records.map((rec) => rec.resId).filter((resId) => resIds.includes(resId));
        if (held.length) {
            await this.siblingList.addAndRemove({ remove: held });
        }
    }

    getTagProps(record) {
        const props = super.getTagProps(record);
        if (!this.props.readonly) {
            props.onDragStart = (ev) => {
                draggedTag = { field: this.props.name, resId: record.resId };
                if (ev.dataTransfer) {
                    ev.dataTransfer.effectAllowed = "move";
                    // Some browsers start no drag without data of some kind.
                    ev.dataTransfer.setData("text/plain", record.data.display_name || "");
                }
            };
            props.onDragEnd = () => {
                draggedTag = null;
            };
        }
        return props;
    }

    acceptsDrop() {
        return !this.props.readonly && draggedTag?.field === this.props.exclusiveWith;
    }

    onDragOver(ev) {
        if (this.acceptsDrop()) {
            ev.preventDefault();
            if (ev.dataTransfer) {
                ev.dataTransfer.dropEffect = "move";
            }
            this.dropState.over = true;
        }
    }

    onDragLeave(ev) {
        if (!ev.currentTarget.contains(ev.relatedTarget)) {
            this.dropState.over = false;
        }
    }

    async onDrop(ev) {
        this.dropState.over = false;
        if (!this.acceptsDrop()) {
            return;
        }
        ev.preventDefault();
        const { resId } = draggedTag;
        draggedTag = null;
        await this.props.record.data[this.props.name].addAndRemove({ add: [resId] });
        await this.releaseFromSibling([resId]);
    }
}

export const exclusiveTagsField = {
    ...many2ManyTagsField,
    component: ExclusiveTagsField,
    extractProps(fieldInfo, dynamicInfo) {
        return {
            ...many2ManyTagsField.extractProps(fieldInfo, dynamicInfo),
            exclusiveWith: fieldInfo.options.exclusive_with,
        };
    },
};

registry.category("fields").add("ems_exclusive_tags", exclusiveTagsField);
