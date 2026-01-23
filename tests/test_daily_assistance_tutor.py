# -*- coding: utf-8 -*-
from odoo.tests import common, Form

#TRansactionCase hace que no se guarden los registros en BBDD al acabar las pruebas
class TestEmsAttendanceSession(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super(TestEmsAttendanceSession, cls).setUpClass()
        
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Profesor Test',
            'employee_type': 'teacher',
            'work_email': 'teacher@test.com'
        })

        cls.student = cls.env['res.partner'].create({
            'name': 'Alumno Test',
            'email': 'student@test.com',
            'tutor_id': cls.teacher.id
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
            'study_id': cls.study.id
        })

        cls.enrollment = cls.env['ems.enrollment'].create({
            'student_id': cls.student.id,
            'group_id': cls.group.id,
            'subject_id': cls.subject.id
        })

        ''' Error por vista XML segun Gemini
        # --- CREAR TEMPLATE DISPARANDO EL ONCHANGE ---
        template_form = Form(self.env['ems.attendance_template'])
        template_form.teacher_id = self.teacher
        template_form.group_id = self.group
        template_form.subject_id = self.subject # <--- AQUÍ SALTA TU FUNCIÓN _fill_students
        template_form.space_id = self.env['ems.space'].browse(1) # Mejor crear uno real
        template_form.start_date = '2025-11-01'
        template_form.end_date = '2026-01-01'
        
        self.template = template_form.save()

        '''

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
        
        # Usamos Form para simular la interfaz de usuario. Esto disparará los @api.onchang (Idea de gemini)
        session_form = Form(self.env['ems.attendance_session'])

        session_form.session_teacher_id = self.teacher
        session_form.attendance_schedule_id = self.schedule

        #Hay un estudiante en la lista        
        self.assertEqual(len(session_form.attendance_status_ids), 1)

        #Guarda la sesion en base de datos
        session = session_form.save()

        self.assertEqual(session.attendance_status_ids[0].student_id.id, self.student.id, "El alumno debe coincidir")
        self.assertTrue(session.id, "La sesión debería haberse creado")

    def test_notifications_creation(self):
        """ Prueba: Al crear la sesión, se deben generar los registros de Issues para notificaciones """
        
        session_form = Form(self.env['ems.attendance_session'])
        session_form.attendance_schedule_id = self.schedule
        session_form.session_teacher_id = self.teacher
        
        with session_form.attendance_status_ids.edit(0) as line:
            line.status = 'm_miss'

        session = session_form.save()

        issue_tutor = self.env['ems.attendance_issue_tutor'].search([
            ('tutor_id', '=', self.student.tutor_id.id), 
            ('issue_date', '=', session.date)
        ])
        
        self.assertTrue(issue_tutor, "ERROR: No se creó el registro de informe para el tutor.")
        self.assertEqual(len(issue_tutor), 1, "Debería haber exactamente 1 informe para este tutor hoy.")

        issue_status = self.env['ems.attendance_issue_status'].search([
            ('attendance_status_id', 'in', session.attendance_status_ids.ids)
        ])
        
        self.assertTrue(issue_status, "ERROR: No se creó el detalle de la incidencia (ems.attendance_issue_status).")
        
        self.assertEqual(issue_status[0].attendance_status, 'm_miss', "El estado guardado en la incidencia debería ser 'm_miss'")
        self.assertEqual(issue_status[0].attendance_issue_student_id.student_id.id, self.student.id, "La incidencia debe ser del alumno correcto")
