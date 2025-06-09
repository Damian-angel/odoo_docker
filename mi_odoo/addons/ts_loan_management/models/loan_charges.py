from odoo import fields, models, api
from odoo.exceptions import ValidationError


class LoanChargesType(models.Model):
    _name = 'loan.charges.technians'
    _description = 'Loan Charges'

    name = fields.Char('Charge Name')
    description = fields.Char('Description')
    charge_tax_id = fields.Many2one('account.tax')
    charge_journal_id = fields.Many2one('account.journal')
    charge_account_id  = fields.Many2one('account.account')
    charge_amount_type = fields.Selection([('fixed','Fixed'),('percent','Percent')],default='fixed',string="Charge Type")
    charge_amount = fields.Integer('Amount')
    is_foreclosure = fields.Boolean(string='Is Foreclosure ?')
    
    @api.onchange('charge_amount','charge_amount_type')
    def onchange_charge_amount(self):
        charge_amount_type = self.charge_amount_type
        charge_amount = self.charge_amount
        if(charge_amount_type == 'percent' and charge_amount > 100):
             raise ValidationError("Percentage should not exceed 100")
         
         
    