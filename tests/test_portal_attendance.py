import json
from odoo.tests import HttpCase, tagged

@tagged('post_install', '-at_install')
class TestPortalAttendance(HttpCase):

    def setUp(self):
        super(TestPortalAttendance, self).setUp()
        # 1. Creamos datos de prueba (Un alumno y un nivel)
        self.level = self.env['ems.level'].create({'name': 'Nivel Test', 'acronym': 'TEST'})
        self.study = self.env['ems.study'].create({'name': 'Estudio Test', 'code': 'TEST', 'acronym': 'TEST', 'date': '2025-10-10', 'deprecated': 'f'})
        self.group = self.env['ems.group'].create({'name': 'Nivel Test', 'acronym': 'TEST', 'course':'1', 'level_id': self.level.id, 'study_id': self.study.id})
        
        # Creamos un usuario de portal para probar los permisos reales
        self.portal_user = self.env['res.users'].create({
            'name': 'Alumno Test',
            'login': 'student_test',
            'password': 'student_password',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])] # Grupo Portal
        })
        
        # Asignamos el partner al usuario
        self.student_partner = self.portal_user.partner_id
        self.student_partner.write({
            'level_id': self.level.id,
            'study_id': self.study.id
        })

    def test_portal_wizard_student_report_submit(self):
        self.authenticate('student_test', 'student_password')

        payload = {
            'params': {
                'student_id': self.student_partner.id,
                'level_id': self.level.id,
                'study_id': self.study.id,
                'group_id': self.group.id
            },
        }

        # PASO 1: Crear el Wizard
        response = self.url_open(
            '/portal/wizard/submit', 
            data=json.dumps(payload), 
            headers={'Content-Type': 'application/json'}
        )
        
        json_response = json.loads(response.content)
        
        # Verificamos que el paso 1 fue bien
        self.assertTrue(json_response.get('result'), "Falló la llamada JSON")
        self.assertEqual(json_response['result']['status'], 'ok')
        
        # Obtenemos la URL que devolvió el backend
        pdf_url = json_response['result']['url']
        print(f"URL RECIBIDA: {pdf_url}")

        # PASO 2: Intentar descargar el PDF (Aquí es donde fallará si tienes problemas)
        pdf_response = self.url_open(pdf_url)

        # COMPROBACIONES REALES:
        # 1. Que la respuesta sea 200 OK
        self.assertEqual(pdf_response.status_code, 200, "La URL del PDF devolvió un error (404/403/500)")
        
        # 2. Que lo que devuelve sea realmente un PDF
        # Odoo suele devolver 'application/pdf' o 'application/pdf; ...'
        content_type = pdf_response.headers.get('Content-Type', '')
        self.assertIn('application/pdf', content_type, f"Se esperaba un PDF, se recibió: {content_type}")
        
        # 3. Que el archivo tenga contenido (no esté vacío)
        self.assertTrue(len(pdf_response.content) > 100, "El PDF parece estar vacío")