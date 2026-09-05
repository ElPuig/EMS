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
    'website': "https://github.com/ElPuig/EMS",
    #icon authory: thanks to Memed_Nurrohmad (https://pixabay.com/es/vectors/sombrero-graduaci%C3%B3n-gorra-educaci%C3%B3n-1674894/)

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Educational',
    'version': '18.0.0.23.3',    #18.0 means the Odoo version; x.y.z means 'breaking.feature.fix'. The '0.y.z' is for alpha/beta pre-release.

    # any module necessary for this one to work correctly
    # only 'base_setup', 'hr', 'auth_oauth' are needed. The rest are installed sometimes (and sometimes nor) and I don't know why, so I decided to install all manyally in order to avoid errors.
    'depends': [
        'base_setup', 
        'hr', 
        'hr_org_chart', 
        'auth_oauth', 
        'contacts', 
        'project', 
        'mass_mailing', 
        'survey', 
        'hr_attendance',
        'queue_job',
        'sale_management',
        'sale_pdf_quote_builder',
        'account',
        'base_vat',
        'spreadsheet_dashboard',
        'partner_firstname',
        'partner_multi_relation'
    ],
    
    # just for debugging
    'external_dependencies': {
        'python': [
            'lxml',
            'lxml_html_clean',
            'phonenumbers',
            'openpyxl'
        ],
    },
    
    # always loaded
   'data': [
        'security/groups.xml',
        'security/rules/attendance.xml',
        'security/rules/coexistence.xml',
        'security/rules/communications.xml',
        'security/rules/contacts.xml',
        'security/rules/employees.xml',
        'security/rules/grading.xml',
        'security/rules/planning.xml',
        'security/rules/portal.xml',
        'security/rules/task_assignment.xml',
        'security/ir.model.access.csv',


        'views/menu.xml',

        # Before form.xml: the settings button references this action by XML ID.
        'views/settings/course.xml',
        'views/settings/course_transition_wizard.xml',
        'views/settings/form.xml',
        'views/settings/hr_attendance_form.xml',
        'views/settings/hr_employees_form.xml',
        'views/settings/res_users_form.xml',
        'views/settings/menu.xml',                                    
        
        'views/community/contact/search.xml', # Should be loaded prior to menu
        'views/community/menu.xml',  
            'views/community/configuration/menu.xml',            

            'views/community/employee/menu.xml',
            'views/community/employee/kanban.xml',
            'views/community/employee/list.xml',
            'views/community/employee/search.xml',
            'views/community/employee/form.xml',
            'views/community/employee/departure_reason.xml',

            'views/community/workgroup/list.xml',
            'views/community/workgroup/form.xml',  
            'views/community/workgroup/menu.xml',  
            
            'views/community/contact/list.xml',            
            'views/community/contact/form.xml',
            'views/community/contact/relation_wizard.xml',
            'views/community/contact/kanban.xml',
            'views/community/contact/menu.xml',
            'views/community/contact/import_wizard.xml',
            'views/community/contact/update_wizard.xml',            
            'views/community/contact/portal_access_wizard.xml',
            'views/community/contact/native_action_bindings.xml',
            'views/community/contact/exit_wizards.xml',
            'views/community/contact/student_document.xml',

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
            'views/community/department/form.xml',
            'views/community/department/kanban.xml',
                        
            'views/community/work_location/menu.xml',
            'views/community/employmenttypes/menu.xml',        
            
            'views/community/working_schedules/list.xml',
            'views/community/working_schedules/search.xml',
            'views/community/working_schedules/form.xml',
            'views/community/working_schedules/attendance_form.xml',
            'views/community/working_schedules/import_wizard.xml',
            'views/community/working_schedules/menu.xml',

            'views/community/non_teaching_type/list.xml',
            'views/community/non_teaching_type/form.xml',
            'views/community/non_teaching_type/menu.xml',
            'views/community/employee/user_profile_form.xml',

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
            'views/planning_grading/grading/list.xml',
            'views/planning_grading/grading/form.xml',
            'views/planning_grading/grading/search.xml',
            'views/planning_grading/grading/menu.xml',
            'views/planning_grading/grading/wizard.xml',
            'views/planning_grading/grading/import_wizard.xml',
            'views/planning_grading/grading/em_wizard.xml',
            'views/planning_grading/grading/year_record/list.xml',
            'views/planning_grading/grading/year_record/form.xml',
            'views/planning_grading/grading/year_record/search.xml',
            'views/planning_grading/grading/year_record/menu.xml',

            'views/communications/menu.xml',

            'views/communications/surveys/header/list.xml',
            'views/communications/surveys/header/search.xml',
            'views/communications/surveys/header/form.xml',
            'views/communications/surveys/header/menu.xml',
            'views/communications/surveys/block/form.xml',
            'views/communications/surveys/recipient/form.xml',
            

        # 'views/community/tracking/list.xml',
        # 'views/community/tracking/form.xml',  
        # 'views/community/tracking/menu.xml',     

                   

        'views/attendance/menu.xml',
            'views/attendance/configuration/menu.xml',

            'views/attendance/attendance_status/menu.xml',
            'views/attendance/attendance_status/list.xml',
            'views/attendance/attendance_status/form.xml',

            'views/attendance/attendance_template/menu.xml',
            'views/attendance/attendance_template/list.xml',
            'views/attendance/attendance_template/form.xml',
            'views/attendance/attendance_template/search.xml', 

            'views/attendance/attendance_session/menu.xml',
            'views/attendance/attendance_session/list.xml',
            'views/attendance/attendance_session/form.xml',                     
            'views/attendance/attendance_session/search.xml',                                                 
            #'views/attendance/attendance_session/calendar.xml',     

            'views/attendance/attendance_schedule/form.xml',

            'views/attendance/attendance_justification/menu.xml',
            'views/attendance/attendance_justification/list.xml',
            'views/attendance/attendance_justification/form.xml',
            'views/attendance/attendance_justification/search.xml',

            'views/attendance/attendance_correction/menu.xml',
            'views/attendance/attendance_correction/list.xml',
            'views/attendance/attendance_correction/form.xml',
            'views/attendance/attendance_correction/hr_attendance_form.xml',

            'views/attendance/guard_duty_board/menu.xml',
            'reports/attendance/report_guard_duty_board.xml',

            'views/attendance/attendance_issue/menu.xml',
            'views/attendance/attendance_issue/list.xml',
            'views/attendance/attendance_issue/form.xml',

            'views/attendance/attendance_notification/menu.xml',  
            'views/attendance/attendance_notification/list.xml',               

            'views/attendance/attendance_reports/analysis_views.xml',
            'views/attendance/attendance_reports/menu.xml',
            'views/attendance/attendance_reports/wizard.xml',

            'views/communications/notice/list.xml',
            'views/communications/notice/search.xml',
            'views/communications/notice/form.xml',

        'views/coexistence/strike/list.xml',
        'views/coexistence/strike/form.xml',
        'views/coexistence/strike/menu.xml',
        'views/coexistence/strike_reason/list.xml',
        'views/coexistence/strike_reason/form.xml',
        'views/coexistence/strike_reason/menu.xml',

        'views/academic_management/menu.xml',
            'views/academic_management/enrollment/enrollment_form.xml',
            'views/academic_management/enrollment/enrollment_list.xml',
            'views/academic_management/enrollment/list_tutor.xml',
            'views/academic_management/enrollment/enrollment_proposal_wizard.xml',
            'views/academic_management/enrollment/enrollment_search.xml',
            'views/academic_management/enrollment/menu.xml',
            'views/academic_management/enrollment/no_destination.xml',
            'views/academic_management/enrollment/applicants.xml',
            'views/academic_management/enrollment/applicant_import_wizard.xml',
            'views/academic_management/enrollment_configuration/enrollment_items_form.xml',
            'views/academic_management/enrollment_configuration/enrollment_items_view.xml',
            'views/academic_management/enrollment_configuration/enrollment_authorization_search.xml',
            'views/academic_management/enrollment_configuration/enrollment_authorization_view.xml',
            'views/academic_management/enrollment_configuration/enrollment_authorization_form.xml',
            'reports/authorizations/report_authorization_certificate.xml',
            'reports/contacts/report_google_credentials.xml',
            'reports/employees/report_google_credentials_employee.xml',
            'reports/employees/report_working_schedule.xml',
            'reports/contacts/report_group_schedule.xml',
        'reports/enrollment/templates/report_enrollment_template.xml',
        'reports/enrollment/enrollment.xml',
            'views/academic_management/enrollment_configuration/enrollment_template_form.xml',
            'views/academic_management/enrollment_configuration/enrollment_template_view.xml',
            'views/academic_management/enrollment_configuration/menu.xml',
            'views/academic_management/task_assignment/view.xml',
            'views/academic_management/task_assignment/menu.xml',

        'views/sales/product_view.xml',
        'views/accounting/payment_term_views.xml',
        'views/accounting/enrollment_collections.xml',

        'views/portal/portal_main.xml',
            'views/portal/frontend_branding.xml',
            'views/portal/portal_loading_overlay.xml',
            'views/portal/portal_header.xml',
            'views/portal/portal_account_readonly.xml',
            'views/portal/portal_enrollment_draft.xml',
            'views/portal/portal_enrollment_confirmed.xml',
            'views/portal/portal_comms.xml',
            'views/portal/portal_documentation.xml',
            'views/portal/portal_under_construction.xml',

        'views/documentation/menu.xml',       
            'views/documentation/minutes/menu.xml',       
            'views/documentation/minutes/list.xml',       
            'views/documentation/minutes/form.xml',   

        'views/shared/attachment/form.xml',  


        ### Mailing templates ###
        'mails/communications/communication.xml',        
        'mails/attendance/attendance_issue_status.xml',
        'mails/attendance/attendance_issue_rectification.xml',
        'mails/attendance/attendance_issue_tutor.xml',
        'mails/coexistence/strike_notification.xml',
        'mails/coexistence/strike_escalation.xml',
        'mails/enrollment/enrollment_send.xml',

        ### Reports templates ###
        'reports/attendance/templates/sumary_table.xml',
        'reports/attendance/templates/details_table.xml',
        'reports/attendance/templates/detail_section.xml',

        ### Reports entries ###
        'reports/attendance/session.xml', 
        'reports/attendance/student.xml',
        'reports/attendance/subject.xml',  
        'reports/attendance/group.xml',              
        
        ### Data entries (do not alter the order) ###
        'data/main/res.partner.category.csv',
        'data/main/resync_lifecycle_categories.xml',
        'data/main/ems.space_type.csv',
        'data/main/hr.work.location.csv',
        'data/main/hr.departure.reason.csv',
        'data/main/res.partner.relation.type.csv',
        'data/main/mail.activity.type.csv',
        'data/main/mail.template-google_welcome.csv',
        'data/main/product.category.csv',
        'data/main/ems.strike.reason.csv',
        'data/main/ems.attendance_status.csv',
        'data/main/ems.non_teaching_type.csv',
        'data/main/ems.schedule_framework_default.xml',

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
        'data/cat/product.template-generic.csv',
        'data/cat/ems_enrollment_template_data.xml',
        
        
        # Custom data entries (adapt it to your needs, for example, ESO subjects can differ between centers)        
        'data/custom/eso/ems.subject.csv',
        'data/custom/eso/ems.study.csv',
        'data/custom/btx/ems.subject.csv',
        'data/custom/btx/ems.study.csv',
        'data/custom/ccff/ems.subject.csv',
        'data/custom/ccff/ems.study.csv',
        'data/custom/ccff/ems.outcome.csv',
        'data/custom/ccff/ems_enrollment_template_opt.xml',
        'data/custom/ccff/ems.planning-smx.csv',
        'data/custom/ccff/ems.planning_outcome-smx.csv',
        'data/custom/ccff/ems.planning-asix.csv',
        'data/custom/ccff/ems.planning_outcome-asix.csv',
        'data/custom/ccff/ems.planning-dam.csv',
        'data/custom/ccff/ems.planning_outcome-dam.csv',
        'data/custom/ccff/ems.planning-daw.csv',
        'data/custom/ccff/ems.planning_outcome-daw.csv',
        'data/custom/ccff/ems.planning-ga.csv',
        'data/custom/ccff/ems.planning_outcome-ga.csv',
        'data/custom/ccff/ems.planning-aif.csv',
        'data/custom/ccff/ems.planning_outcome-aif.csv',
        'data/custom/ccff/ems.planning-ad.csv',
        'data/custom/ccff/ems.planning_outcome-ad.csv',
        'data/custom/ccff/ems.planning-sa.csv',
        'data/custom/ccff/ems.planning_outcome-sa.csv',
        'data/custom/ccff/ems.planning-opt.csv',
        'data/custom/ccff/ems.planning_outcome-opt.csv',
        'data/custom/ems.space.csv',
        'data/custom/ems.group.csv',
        'data/custom/hr.department.csv',
        'data/custom/resource.calendar.csv',
        'data/custom/resource.calendar.attendance.csv',
        'data/custom/res.company.csv',
        'data/custom/res.partner.csv',
        'data/custom/ems.course.csv',
        'data/custom/crm.team.csv',
        'data/custom/ems.authorization.template.csv',
        'data/custom/ir.sequence-enrollment_number.csv',

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
    'post_init_hook': 'post_init_hook',
    
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
        # 'demo/attendance/attendance_session_header.xml',
        # 'demo/attendance/attendance_session_line.xml',
    ],   
    'assets': {
        'web.assets_backend': [
            'ems/static/src/xml/backend/**/*',
            'ems/static/src/css/backend/**/*',
            'ems/static/src/js/backend/**/*',
        ],
        'web.assets_frontend': [
           'ems/static/src/css/frontend/**/*',
           'ems/static/src/scss/frontend/**/*',
        ],
        'web.assets_common': [
            #'ems/static/src/css/**/*',
        ],
        'web.assets_tests': [
            'ems/static/tests/tours/**/*',
        ],
    },
}
