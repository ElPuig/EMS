# -*- coding: utf-8 -*-
{
    'name': "EMS: Educational Management System",

    'summary': """
        Provides a free, open-source, comprehensive and intuitive environment in order to manage an educational center.
    """,

    'description': """
        The EMS's main objective is to provide a free, open-source, comprehensive and intuitive environment in order to manage an educational center. To achieve that, a group of bold teachers from 'Institut Puig Castellar' (Santa Coloma de Gramenet, Barcelona, Spain) is developing this Odoo module as part of the Quality and Continuous Improvement Project (Q&CIP or PQiMC in our local language: Catalan).
    """,

    'author': "El Puig",
    'website': "https://github.com/custom/EMS",
    #icon authory: thanks to Memed_Nurrohmad (https://pixabay.com/es/vectors/sombrero-graduaci%C3%B3n-gorra-educaci%C3%B3n-1674894/)

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Educational',
    'version': '18.0.0.0.1',    #18.0 means the Odoo version; x.y.z means 'breaking.feature.fix'. The '0.y.z' is for alpha/beta pre-release. 

    # any module necessary for this one to work correctly
    # only 'base_setup', 'hr', 'auth_oauth' are needed. The rest are installed sometimes (and sometimes nor) and I don't know why, so I decided to install all manyally in order to avoid errors.
    'depends': ['base_setup', 'hr', 'hr_org_chart', 'auth_oauth', 'contacts', 'project', 'mass_mailing', 'survey', 'hr_attendance'],
    
    # just for debugging
    'external_dependencies': {
        'python': ['debugpy'],
    },
    
    # always loaded
   'data': [
        'security/groups.xml',        
        'security/ir.model.access.csv',                        
        
        'views/menu.xml',

        'views/settings/form.xml',
        'views/settings/menu.xml',                                    
        
        'views/community/contact/search.xml', # Should be loaded prior to menu
        'views/community/menu.xml',  
            'views/community/configuration/menu.xml',            

            'views/community/employee/menu.xml', 
            'views/community/employee/kanban.xml',        
            'views/community/employee/list.xml',
            'views/community/employee/form.xml',                                      

            'views/community/workgroup/list.xml',
            'views/community/workgroup/form.xml',  
            'views/community/workgroup/menu.xml',  
            
            'views/community/contact/list.xml',
            'views/community/contact/form.xml',            
            'views/community/contact/kanban.xml',
            'views/community/contact/menu.xml',

            'views/community/group/list.xml',
            'views/community/group/form.xml',  
            'views/community/group/menu.xml',  

            'views/community/enrollment/list.xml',
            'views/community/enrollment/form.xml',
            'views/community/enrollment/menu.xml',

            'views/community/teaching/list.xml',
            'views/community/teaching/form.xml',
            'views/community/teaching/menu.xml',

            'views/community/job/list.xml',
            'views/community/job/form.xml', 
            'views/community/job/menu.xml',    

            'views/community/role/list.xml',
            'views/community/role/form.xml',
            'views/community/role/menu.xml',
                
            'views/community/department/menu.xml',
            'views/community/department/list.xml',
            'views/community/department/search.xml',
                        
            'views/community/work_location/menu.xml',
            'views/community/employmenttypes/menu.xml',        
            
            'views/community/working_schedules/import_wizard.xml',
            'views/community/working_schedules/menu.xml',

            'views/community/subject/list.xml',
            'views/community/subject/search.xml',
            'views/community/subject/form.xml',
            'views/community/subject/menu.xml',            

            'views/community/study/list.xml',
            'views/community/study/search.xml',
            'views/community/study/form.xml',     
            'views/community/study/menu.xml',        
        
            'views/community/level/list.xml',
            'views/community/level/form.xml',
            'views/community/level/menu.xml',   

            'views/community/space/menu.xml',

            'views/community/space/list.xml',
            'views/community/space/search.xml',
            'views/community/space/form.xml',            

            'views/community/space_type/list.xml',
            'views/community/space_type/form.xml',
            'views/community/space_type/menu.xml',    

            'views/community/content/form.xml', 
            'views/community/criteria/form.xml',
            'views/community/outcome/form.xml',

            'views/planning_grading/menu.xml',
            'views/planning_grading/planning/list.xml',
            'views/planning_grading/planning/form.xml',
            'views/planning_grading/planning/menu.xml',

        # 'views/community/tracking/list.xml',
        # 'views/community/tracking/form.xml',  
        # 'views/community/tracking/menu.xml',     

                   

        'views/attendance/menu.xml',
            'views/attendance/configuration/menu.xml',

            'views/attendance/attendance_template/menu.xml',
            'views/attendance/attendance_template/list.xml',
            'views/attendance/attendance_template/form.xml',

            'views/attendance/attendance_session/list.xml',
            'views/attendance/attendance_session/form.xml',
            'views/attendance/attendance_session/calendar.xml',
            'views/attendance/attendance_session/menu.xml',
            'views/attendance/attendance_session/justification_wizard.xml',            

            'views/attendance/attendance_status/list.xml',
            'views/attendance/attendance_status/form.xml',
            'views/attendance/attendance_status/menu.xml',                   

            'views/attendance/attendance_schedule/form.xml',

            'views/attendance/attendance_reports/menu.xml',
            'views/attendance/attendance_reports/student_wizard.xml', 
            'views/attendance/attendance_reports/subject_wizard.xml', 
            'views/attendance/attendance_reports/group_wizard.xml', 
            
        'views/documentation/menu.xml',       
            'views/documentation/minutes/menu.xml',       
            'views/documentation/minutes/list.xml',       
            'views/documentation/minutes/form.xml',   

        'views/shared/attachment/form.xml',  

        ### Reports templates ###
        'reports/attendance/templates/sumary_table.xml', 
        'reports/attendance/templates/details_table.xml', 

        ### Reports entries ###
        'reports/attendance/session.xml', 
        'reports/attendance/student.xml',
        'reports/attendance/subject.xml',  
        'reports/attendance/group.xml',              
        
        ### Data entries (do not alter the order) ###
        'data/main/ems.space_type.csv',    
        'data/main/hr.work.location.csv',    

        'data/cat/attachments/asix/ir.attachment.csv',
        'data/cat/attachments/dam/ir.attachment.csv',
        'data/cat/attachments/daw/ir.attachment.csv',
        'data/cat/attachments/dev/ir.attachment.csv',
        'data/cat/attachments/smx/ir.attachment.csv',
        'data/cat/attachments/ga/ir.attachment.csv',
        'data/cat/attachments/aif/ir.attachment.csv',
        'data/cat/attachments/ad/ir.attachment.csv',
        'data/cat/attachments/sa/ir.attachment.csv',
        'data/cat/attachments/ao/ir.attachment.csv',
        
        'data/cat/attachments/eso/ir.attachment.csv',
        'data/cat/attachments/btx/ir.attachment.csv',
        'data/cat/attachments/btx/common/ir.attachment.csv',
        'data/cat/attachments/btx/mandatory/ir.attachment.csv',
        'data/cat/attachments/btx/modality/general/ir.attachment.csv',
        'data/cat/attachments/btx/modality/humanistic/ir.attachment.csv',
        'data/cat/attachments/btx/modality/musical arts/ir.attachment.csv',
        'data/cat/attachments/btx/modality/plastic arts/ir.attachment.csv',
        'data/cat/attachments/btx/modality/sciences and technology/ir.attachment.csv',
        
        'data/cat/ems.subject.csv',
        'data/cat/ems.level.csv',
        'data/cat/ems.study.csv',
        'data/cat/ems.content.csv',
        'data/cat/ems.outcome.csv',    
        'data/cat/ems.role.csv',    
        'data/cat/ems.workgroup.csv',    
        'data/cat/hr.job.csv',
        
        # Custom data entries (adapt it to your needs, for example, ESO subjects can differ between centers)        
        'data/custom/eso/ems.subject.csv',
        'data/custom/eso/ems.study.csv',
        'data/custom/btx/ems.subject.csv',
        'data/custom/btx/ems.study.csv',
        'data/custom/ems.space.csv',
        'data/custom/ems.group.csv',
        'data/custom/ems.role.csv',
        'data/custom/hr.department.csv',
        'data/custom/res.company.csv',

        # Teacher's data (teaching = subject x teacher x group)
        #'data/custom/hr.employee.csv',        
        #'data/custom/ems.teaching.csv',
        
        # Student's data (enrollment = subject x student x group)
        # 'data/custom/ccff/dam1a/res.partner.csv',
        # 'data/custom/ccff/dam1a/ems.enrollment.csv',
        # 'data/custom/ccff/daw1a/res.partner.csv',
        # 'data/custom/ccff/daw1a/ems.enrollment.csv',
    ],
    'license': 'AGPL-3',
    'installable': True,
    'application': True,
    
    # only loaded in demonstration mode (only loaded when installed, ignored when updated)
    'demo': [
        # this order is needed due dependencies
        'demo/shared/attachment.xml',

        'demo/curriculum/level.xml',
        'demo/curriculum/study.xml',
        'demo/curriculum/subject.xml',
        'demo/curriculum/content.xml',

        'demo/facilities/space_type.xml',         
        'demo/facilities/space.xml',         

        'demo/contacts/group.xml',        
        'demo/contacts/company.xml',        
        
        'demo/employees/teaching.xml',   
        'demo/employees/job.xml',
        'demo/employees/department.xml',
        'demo/employees/work_location.xml',
        'demo/employees/teacher.xml',
        'demo/employees/pas.xml',
        'demo/employees/role.xml', 
        'demo/employees/employee.xml',  
        'demo/employees/workgroup.xml',   

        'demo/contacts/student.xml',
        'demo/contacts/provider.xml',
        'demo/contacts/enrollment.xml',

        # 'demo/attendance/attendance_template.xml',
        # 'demo/attendance/attendance_schedule.xml',
        # 'demo/attendance/attendance_session.xml',
        # 'demo/attendance/attendance_status.xml',
    ],   
    'assets': {       
        'web.assets_backend': [
            'ems/static/src/xml/backend/**/*',
            'ems/static/src/css/backend/**/*',
            'ems/static/src/js/backend/**/*', 
        ],       
        'web.assets_frontend': [
           'ems/static/src/css/frontend/**/*',
        ],
        'web.assets_common': [
            #'ems/static/src/css/**/*',      
        ],
    },
}
