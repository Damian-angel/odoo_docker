from odoo import api, fields, models
class ResCompany(models.Model):
    _inherit = "res.company"

    interval_in_loan = fields.Boolean(string='Interval In Loan?')
