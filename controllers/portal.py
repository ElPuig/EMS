# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

class EMSPortalController(CustomerPortal):

    # -------------------------------------------------------------
    # (Gestión de Matrículas)
    # -------------------------------------------------------------
    @http.route(['/my/gestion-matriculas'], type='http', auth="user", website=True)
    def portal_gestion_matriculas(self, **kw):
        # 1. Preparamos los valores base de la página (usuario actual, etc.)
        values = self._prepare_portal_layout_values()
        
        # 2. Le pedimos a Odoo que calcule los contadores de los documentos nativos
        try:
            home_values = self._prepare_home_portal_values(counters=['quotation', 'order', 'invoice'])
        except TypeError:
            home_values = self._prepare_home_portal_values()
            
        values.update(home_values)
        
        # 3. Le damos un nombre a la página (para el menú y las migas de pan)
        values['page_name'] = 'gestion_matriculas'
        
        # 4. Renderizamos nuestra nueva vista XML
        return request.render("ems.portal_gestion_matriculas", values)

    # -------------------------------------------------------------
    # (Páginas en Construcción)
    # -------------------------------------------------------------
    @http.route([
        '/my/asistencia', 
        '/my/calificaciones', 
        '/my/comunicaciones', 
        '/my/documentacion'
    ], type='http', auth='user', website=True)
    def under_construction(self, **kwargs):
        # Le pasamos el nombre de la página para que la franja naranja del menú 
        # siga marcando el botón correcto aunque estemos en esta vista genérica
        values = self._prepare_portal_layout_values()
        
        # Renderizamos nuestra nueva vista de "En desarrollo"
        return request.render('ems.portal_under_construction_page', values)