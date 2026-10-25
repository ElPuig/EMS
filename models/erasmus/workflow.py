# -*- coding: utf-8 -*-
"""What the Erasmus+ workflow sets by itself (states, decisions, signatures, frozen values) and what
a record keeps as evidence. Plain helpers, called from the models' create(), write() and unlink();
see docs/en/developers/erasmus/erasmus.md, "Workflow fields and evidence".

Audit 2026-10-25 (R-25): `readonly=True` only hides a field in the views; the ORM still accepts it
from anyone with write access, which is what an RPC call does. And a context key is no proof that
the workflow is writing: a client sends any context it likes with call_kw. So the actions write
these fields as superuser (after their own checks), and only a superuser write gets through."""

from odoo import _, models
from odoo.exceptions import AccessError, UserError
from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG

NOT_WORKFLOW = set(models.MAGIC_COLUMNS) | {'display_name'}


def workflow_fields(model, extra=('state',)):
    """The fields only the workflow writes: every stored field the model declares read-only (not a
    computed nor a related one), and `extra` (the state, shown read-only by its status bar)."""
    return {name for name, field in model._fields.items()
            if field.store and field.readonly and not field.compute and not field.related
            and name not in NOT_WORKFLOW} | {name for name in extra if name in model._fields}


def _refuse(model, names):
    labels = ", ".join(sorted(model._fields[name]._description_string(model.env) for name in names))
    raise AccessError(_("These fields of %(model)s are set by its actions, never by hand: %(fields)s.",
                        model=model._description, fields=labels))


def check_workflow_write(records, vals, extra=('state',)):
    if not records.env.su and (names := workflow_fields(records, extra) & set(vals)):
        _refuse(records, names)


def check_workflow_create(model, vals_list, extra=('state',)):
    """A new record starts as the workflow starts it: a workflow field is only accepted with its
    default value (a form sends the status bar's initial state)."""
    if model.env.su:
        return
    names = workflow_fields(model, extra)
    for vals in vals_list:
        given = names & set(vals)
        defaults = model.default_get(list(given)) if given else {}
        if wrong := {name for name in given if (vals[name] or False) != (defaults.get(name) or False)}:
            _refuse(model, wrong)


def check_kept(records, held):
    """Never delete `held` (the part of `records` that holds evidence of a record: a file, a valid
    document, a signature, a draw, a submitted evaluation...), not even as superuser: the database
    cascade from a parent would skip the children's own guards. Only uninstalling the module does."""
    if held and not records.env.context.get(MODULE_UNINSTALL_FLAG):
        raise UserError(_("These records keep evidence of an Erasmus+ record and cannot be deleted (cancel "
                          "or withdraw them instead): %(records)s.", records=", ".join(held.mapped('display_name'))))
