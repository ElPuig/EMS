# -*- coding: utf-8 -*-
from odoo.tests import common, Form

#TransactionCase hace que no se guarden los registros en BBDD al acabar las pruebas
class TestEmsAttendanceSession(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super(TestEmsAttendanceSession, cls).setUpClass()
        
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Profesor Test',
            'employee_type': 'teacher',
            'work_email': 'teacher@test.com'
        })
        
        cls.level = cls.env['ems.level'].create({
            'name': 'Superior Test', 
            'acronym': 'ST'
        })

        cls.study = cls.env['ems.study'].create({
            'name': 'Estudio Test', 
            'code': 'TEST', 
            'acronym': 'TEST', 
            'date': '2025-10-10', 
            'deprecated': 'f'
        })

        cls.subject = cls.env['ems.subject'].create({
            'name': 'Subject Test',
            'code': 'SJT',
            'acronym': 'SubT'
        })

        cls.group = cls.env['ems.group'].create({
            'name': 'Grupo Test', 
            'acronym': '1TEST', 
            'course':'1', 
            'level_id': cls.level.id, 
            'study_id': cls.study.id,
            'tutor_id': cls.teacher.id
        })

        cls.student1 = cls.env['res.partner'].create({
            'name': 'Alumno 1 Test',
            'email': 'student1@test.com',
            'main_group_id': cls.group.id
        })
        
        cls.student2 = cls.env['res.partner'].create({
            'name': 'Alumno 2 Test',
            'email': 'student2@test.com',
            'main_group_id': cls.group.id

        })

        cls.student3 = cls.env['res.partner'].create({
            'name': 'Alumno 3 Test',
            'email': 'student3@test.com',
            'main_group_id': cls.group.id
        })

        cls.students_to_check = [cls.student1, cls.student2, cls.student3]

        cls.enrollment1 = cls.env['ems.enrollment'].create({
            'student_id': cls.student1.id,
            'group_id': cls.group.id,
            'subject_id': cls.subject.id
        })

        cls.enrollment2 = cls.env['ems.enrollment'].create({
            'student_id': cls.student2.id,
            'group_id': cls.group.id,
            'subject_id': cls.subject.id
        })

        cls.enrollment3 = cls.env['ems.enrollment'].create({
            'student_id': cls.student3.id,
            'group_id': cls.group.id,
            'subject_id': cls.subject.id
        })

        cls.template = cls.env['ems.attendance_template'].create({
            'teacher_id': cls.teacher.id,
            'level_id': cls.level.id,
            'study_id': cls.study.id,
            'group_id': cls.group.id,
            'subject_id': cls.subject.id,
            'space_id': 1,
            'start_date': '2025-11-01',
            'end_date': '2026-01-01'
        })
        cls.template._fill_students()

        cls.schedule = cls.env['ems.attendance_schedule'].create({
            'space_id': 1,
            'attendance_template_id': cls.template.id,
            'weekday': '2',
            'start_time': 15,
            'end_time': 16
        })

    def test_create_session_and_load_students(self):
        """ Prueba: Al seleccionar un horario, se deben cargar los estudiantes automáticamente (Onchange) """
        
        # Usamos Form para simular la interfaz de usuario. Esto disparará los @api.onchange (Idea de gemini)
        session_form = Form(self.env['ems.attendance_session_header'])

        session_form.session_teacher_id = self.teacher
        session_form.attendance_schedule_id = self.schedule

        #Hay tres estudiantes en la lista        
        self.assertEqual(len(session_form.attendance_session_line_ids), 3)

        #Guarda la sesion en base de datos
        session = session_form.save()

        for i in range(len(self.students_to_check)):
            self.assertEqual(session.attendance_session_line_ids[i].student_id.id, self.students_to_check[i].id, "El alumno debe coincidir")
            
        self.assertTrue(session.id, "La sesión debería haberse creado")

    def test_notifications_creation(self):
        """ Prueba: Al crear la sesión, se deben generar los registros de Issues para notificaciones """
        
        # Usamos Form para simular la interfaz de usuario. Esto disparará los @api.onchange (Idea de gemini)
        session_form = Form(self.env['ems.attendance_session_header'])
        session_form.attendance_schedule_id = self.schedule
        session_form.session_teacher_id = self.teacher

        #Para cada estudiante, pasamos lista, en esta instancia de 3, ponemos miss a dos
        for i in range(len(session_form.attendance_session_line_ids)):
            with session_form.attendance_session_line_ids.edit(i) as line:
                if line.student_id.id == self.student2.id:
                    line.status = 'a_attended'
                else:
                    line.status = 'm_miss'

        session = session_form.save()

        #Se comprueba si crea el registro del informe a tutor
        issue_tutor = self.env['ems.attendance_issue_tutor'].search([
            ('tutor_id', '=', self.student1.tutor_id.id), 
            ('issue_date', '=', session.date)
        ])
        self.assertEqual(len(issue_tutor),1, "ERROR: No se creó el registro de informe para el tutor o hay mas de uno.")

        #Se comprueba si crea un registro de los informes de estudiante
        for i in range(len(self.students_to_check)):
            if self.students_to_check[i].id != self.student2.id:
                issue_student = self.env['ems.attendance_issue_student'].search([
                    ('attendance_issue_tutor_id', '=', issue_tutor.id), 
                    ('student_id', '=', self.students_to_check[i].id)
                ])
                self.assertEqual(len(issue_student),1, "ERROR: No se creó el registro de informe para el estudiante o hay mas de uno.")

        #Y para ese informe, se comprueba si crea la incidencia de cada alumno (en este caso 2)
        issue_status = self.env['ems.attendance_issue_status'].search([
            ('attendance_session_line_id', 'in', session.attendance_session_line_ids.ids)
        ])
        self.assertEqual(len(issue_status), 2, "Y ese informe deberia tener 2 alumnos")

        #Se comprueba de cada uno si tiene miss y corresponde al estudiante
        for i in range(len(issue_status)):
            for j in range(len(self.students_to_check)):
                if (issue_status[i].attendance_issue_student_id.student_id.id == self.students_to_check[i].id):
                    self.assertEqual(issue_status[i].attendance_status, 'm_miss', "El estado guardado en la incidencia debería ser 'm_miss'")
                    self.assertEqual(issue_status[i].attendance_issue_student_id.student_id.id, self.students_to_check[i].id, "La incidencia debe ser del alumno correcto")

    """
    def test_singleton_batch_write(self):
         
        PRUEBA TÉCNICA (SINGLETON):
        Guardamos primero para tener registros reales y luego intentamos escribir 
        en TODAS las líneas a la vez.
        # 1. Usamos Form para que se disparen los onchange y se rellenen los alumnos
        session_form = Form(self.env['ems.attendance_session_header'])
        session_form.session_teacher_id = self.teacher
        session_form.attendance_schedule_id = self.schedule
        
        # 2. IMPORTANTE: Guardamos (.save()) para que existan en Base de Datos.
        # Si no hacemos save(), son solo "Proxies" en memoria y no aceptan .write()
        session = session_form.save()
        
        lines = session.attendance_session_line_ids
        
        # Verificamos que tenemos líneas reales
        self.assertEqual(len(lines), 3, "Debe haber 3 líneas reales en BBDD para la prueba")

        # 3. EL MOMENTO DE LA VERDAD (BATCH WRITE)
        # Ahora sí podemos usar .write() porque 'lines' son registros de BBDD, no proxies.
        try:
            # Esto envía todos los IDs a tu función 'status_is_notificable' de golpe.
            lines.write({'status': 'm_miss'})
        except ValueError as e:
            self.fail(f"ERROR SINGLETON DETECTADO: Tu código Python no soporta edición masiva.\nError: {e}")

        # 4. Verificaciones
        for line in lines:
            self.assertEqual(line.status, 'm_miss', "El estado debería haber cambiado en BBDD")
            
        # Verificamos los efectos secundarios (issues creados)
        issues_count = self.env['ems.attendance_issue_status'].search_count([
            ('attendance_session_line_id', 'in', lines.ids)
        ])
        self.assertEqual(issues_count, 3, "Se debieron crear 3 incidencias automáticamente")
                """
