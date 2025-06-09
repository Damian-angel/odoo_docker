# -*- coding: utf-8 -*-

{
    'name': 'Loan Management',
    'version': '17.0',
    'author': 'Technians',
    'maintainer': 'Technians Softech Pvt Ltd.',
    'category': 'Accounting',
    "license": "OPL-1",
    'summary': " Efficiently Manage Customer and Supplier Loan with clarity and speed using the ts_loan management module",
    'website': 'https://technians.com/',
    'depends': ['account'],
    'data': [
        'security/loan_security.xml',
        'security/ir.model.access.csv',
        'views/amount_pay.xml',
        'views/full_payment.xml',
        'views/loan_view.xml',
        'views/res_config_settings_views.xml',
        'views/loan_charges.xml',
        'views/loan_charges_lines.xml',
    ],
    'application': True,
    'installable': True,
    'auto_install': False,
    'price': 30.0,
    'currency': 'USD',
    'images': ['static/description/banner.png'],
}