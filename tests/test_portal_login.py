import re
import uuid
import requests
from odoo.tests import HttpCase, tagged

@tagged('post_install', '-at_install')
class TestPortalLogin(HttpCase):

    def setUp(self):
        super(TestPortalLogin, self).setUp()
        
        # 1. Crear usuario único
        self.unique_login = f"student_{str(uuid.uuid4())[:8]}"
        self.password = "password_123"
        
        # Nos aseguramos que tiene acceso al portal
        group_portal = self.env.ref('base.group_portal')

        self.user = self.env['res.users'].create({
            'name': 'Estudiante Login Test',
            'login': self.unique_login,
            'password': self.password,
            'groups_id': [(6, 0, [group_portal.id])]
        })

    def test_login_form_flow(self):
        
        # 1. Limpiar navegador (Cookies fuera)
        self.opener = requests.Session()

        # 2. GET: Pedimos la página de login primero
        # Necesitamos cargarla para obtener la cookie de sesión inicial y el TOKEN CSRF
        login_url = '/web/login'
        response_get = self.url_open(login_url)
        self.assertEqual(response_get.status_code, 200)

        # 3. EXTRAER EL CSRF TOKEN
        # Odoo pone un input hidden: <input type="hidden" name="csrf_token" value="..."/>
        # Usamos una expresión regular para encontrarlo
        csrf_token_match = re.search(r'name="csrf_token" value="([^"]+)"', response_get.text)
        
        if not csrf_token_match:
            self.fail("No se pudo encontrar el token CSRF en la página de login")
            
        csrf_token = csrf_token_match.group(1)
        print(f"Token CSRF obtenido: {csrf_token}")

        # 4. POST: Enviamos los datos del formulario
        payload = {
            'login': self.unique_login,
            'password': self.password,
            'csrf_token': csrf_token,
            'redirect': '/my' # Le decimos a dónde queremos ir tras loguearnos
        }

        # Enviamos la petición POST como si pulsáramos el botón "Log in"
        response_post = self.url_open(login_url, data=payload)

        # 5. VERIFICACIONES
        
        # A) Que la respuesta sea 200 OK
        self.assertEqual(response_post.status_code, 200)

        # B) Que estemos en la página de destino (/my)
        # Si el login falla, Odoo nos deja en /web/login. Si funciona, nos manda a /my
        self.assertIn('/my', response_post.url, "El login falló, no fuimos redirigidos al portal")

        # C) Que el usuario esté autenticado
        # Buscamos su nombre en el HTML (Odoo suele mostrar el nombre de usuario arriba a la derecha)
        self.assertIn('Estudiante Login Test', response_post.text, "El nombre del usuario no aparece en la página")

    def test_login_form_fail(self):
        
        # 1. Limpiar navegador (Cookies fuera)
        self.opener = requests.Session()
        
        # 2. Obtener CSRF (Igual que antes)
        response_get = self.url_open('/web/login')
        csrf_token = re.search(r'name="csrf_token" value="([^"]+)"', response_get.text).group(1)

        # 3. Enviar datos MALOS
        payload = {
            'login': self.unique_login,
            'password': 'WRONG_PASSWORD',
            'csrf_token': csrf_token,
            'redirect': '/my'
        }
        
        response_post = self.url_open('/web/login', data=payload)

        # 4. Verificar que SEGUIMOS en el login (No entró)
        self.assertIn('/web/login', response_post.url)
        
        # Odoo suele mostrar una alerta "Wrong login/password"
        self.assertIn('Wrong login/password', response_post.text)