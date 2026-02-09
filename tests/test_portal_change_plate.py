import json
import uuid
from odoo.tests import HttpCase, tagged

@tagged('post_install', '-at_install')
class TestStudentCarPlate(HttpCase):

    def setUp(self):
        super(TestStudentCarPlate, self).setUp()
        
        # 1. Crear usuario y partner únicos para evitar conflictos
        self.unique_login = f"student_{str(uuid.uuid4())[:8]}"
        self.password = "password_123"
        
        # Grupo Portal
        group_portal = self.env.ref('base.group_portal')

        self.partner = self.env['res.partner'].create({
            'name': 'Estudiante Matricula Test',
            'email': f"{self.unique_login}@test.com",
            'car_plate': 'OLD-PLATE-000' # Valor inicial
        })

        self.user = self.env['res.users'].create({
            'name': 'Estudiante User',
            'login': self.unique_login,
            'password': self.password,
            'partner_id': self.partner.id,
            'groups_id': [(6, 0, [group_portal.id])]
        })

    def test_update_car_plate_json(self):
        
        # 1. Autenticar
        self.authenticate(self.unique_login, self.password)

        # 2. Definir la nueva matrícula
        new_plate = "NEW-1234-XYZ"

        # 3. Preparar el Payload JSON-RPC
        # Odoo requiere estrictamente este formato para rutas type='json'
        payload = {
            "params": {
                "car_plate": new_plate
            },
        }

        # 4. Enviar la petición
        response = self.url_open(
            '/ems/update_student_car_plate',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'}
        )

        # 5. Verificar la respuesta HTTP/JSON
        self.assertEqual(response.status_code, 200, "La petición debería ser exitosa")
        json_response = json.loads(response.content)

        # Verificamos que no hay error en el JSON
        self.assertFalse(json_response.get('error'), f"El servidor devolvió error: {json_response.get('error')}")
        
        # Verificamos que el controlador devolvió True
        self.assertTrue(json_response.get('result'), "El controlador debería devolver True")

        # 6. VERIFICACIÓN EN BASE DE DATOS (Lo más importante)
        # Invalidamos la caché del registro para obligar a Odoo a leer de la BD
        self.partner.invalidate_recordset(['car_plate'])
        
        # Comprobamos que el valor ha cambiado realmente
        self.assertEqual(self.partner.car_plate, new_plate, "La matrícula no se actualizó en la base de datos")