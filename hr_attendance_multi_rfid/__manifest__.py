# -*- coding: utf-8 -*-
# noinspection PyStatementEffect
{
    'name': 'RFID Attendance',
    'version': '0.3',
    'category': 'Human Resources',
    'summary': 'Manage employee attendance',
    'author': 'Polimex',

    'description': """
       Description
       """,

    'website': 'securitybulgaria.com',

    'depends': [ 'base', 'hr', 'hr_rfid', 'hr_attendance', 'hr_holidays_public' ],

    'data': [
        'reports/hr_attendance_theoretical_time_report_views.xml',
        'security/hr_attendance_report_theoretical_time_security.xml',
        'security/ir.model.access.csv',
        'views/hr_attendance_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_rfid_webstack_views.xml',
        'views/hr_rfid_webstack_views.xml',
    ],

    'demo': [ ],

    "images": [
        'static/images/main_screenshot.png',
    ],

    'installable': True,
    'auto_install': False,
}
