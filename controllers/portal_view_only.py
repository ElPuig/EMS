# -*- coding: utf-8 -*-
"""Whoever may only consult the student he is looking at - a minor on his own account, or a family
looking at its adult child who authorized sharing with it - sees his schedule, grades, profile and
the messages addressed to him. Enrollment, authorizations, convalidations and documentation stay
with whoever acts for the student (res.partner._ems_portal_is_view_only). The menu and the home
cards hide them, and every route behind them refuses him here too, since a hidden link protects
nothing."""

import functools

from odoo import _
from odoo.exceptions import AccessError
from odoo.http import request
from odoo.addons.account.controllers.portal import PortalAccount
from odoo.addons.sale.controllers.portal import CustomerPortal as SaleCustomerPortal


def ems_portal_is_view_only():
    """Whether the logged-in portal user may only consult the student he is looking at."""
    return request.env.user.partner_id._ems_portal_is_view_only()


def ems_portal_manage_required(endpoint):
    """Send a view-only portal user back to the portal home instead of running the route.
    Goes below @http.route, so it wraps the endpoint itself."""
    @functools.wraps(endpoint)
    def wrapper(self, *args, **kwargs):
        if ems_portal_is_view_only():
            return request.redirect('/my/home')
        return endpoint(self, *args, **kwargs)
    return wrapper


class EmsPortalViewOnlySale(SaleCustomerPortal):
    """A minor is the customer of his own enrollment (sale.order.partner_id), so native portal
    rules would let him open, sign or decline it and its invoices from /my/quotes, /my/orders
    and /my/invoices. Emptying those lists and refusing the documents covers every native
    route, since they all go through _document_check_access."""

    def _document_check_access(self, model_name, document_id, access_token=None):
        if model_name in ('sale.order', 'account.move') and ems_portal_is_view_only():
            raise AccessError(_("Your family manages the enrollment from its own portal account."))
        return super()._document_check_access(model_name, document_id, access_token=access_token)

    def _prepare_quotations_domain(self, partner):
        if ems_portal_is_view_only():
            return [('id', '=', False)]
        return super()._prepare_quotations_domain(partner)

    def _prepare_orders_domain(self, partner):
        if ems_portal_is_view_only():
            return [('id', '=', False)]
        return super()._prepare_orders_domain(partner)


class EmsPortalViewOnlyAccount(PortalAccount):

    def _get_invoices_domain(self, m_type=None):
        if ems_portal_is_view_only():
            return [('id', '=', False)]
        return super()._get_invoices_domain(m_type)
