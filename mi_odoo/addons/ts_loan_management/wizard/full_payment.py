# Copyright 2018 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_round
from odoo.exceptions import ValidationError

class FullAmountPay(models.TransientModel):
    _name = 'full.amount.pay'
    _description ='Full Amount Pay'

    @api.model
    def _get_default_remaining_amount(self):
        context = dict(self._context)
        loan_obj = self.env['customer.loan']
        if context.get('active_id',False):
            loan_rec = loan_obj.search([('id', '=', context.get('active_id'))])
            if not loan_rec:
                return 0.0
            return loan_rec.total_remaining

    @api.model
    def _default_journal_id(self):
        return self._context.get('default_loan_id') and self._context.get('default_loan_id').journal_id.id or False

    loan_id = fields.Many2one('customer.loan')
    date = fields.Date(required=True, default=fields.Date.today())
    amount = fields.Float(string='Pending Principal', related='loan_id.total_remaining')
    fees = fields.Float(string='Interest')
    total_amount = fields.Float(string='Total Amount',compute='compute_total_amount')
    journal_id = fields.Many2one('account.journal', related='loan_id.loan_journal_id')

    @api.constrains('fees')
    def _check_interest(self):
        if self.fees < 0.00: 
            raise ValidationError(_("Interest Can't Be Greater than Zero(0.00)"))

    @api.depends('amount','fees')
    def compute_total_amount(self):
        for rec in self:
            self.total_amount = self.amount + self.fees

    def modify_emi(self):
        emis = self.env['customer.loan.line'].search([('loan_id','=',self.loan_id.id)], order='due_date asc')
        found_draft = False
        last_emi = None
        for emi in emis:
            if not found_draft and emi.status == 'draft':
                emi.write({
                    'due_date': self.date,
                    'status': 'paid',
                    'remaining': 0.0,
                    'amount': self.amount,
                    'interest': self.fees,
                    'installment': self.amount + self.fees
                })
                last_emi = emi
                found_draft = True
            elif found_draft:
                emi.unlink()
        return last_emi


    def pay_full_amount(self):
        loan_line = self.modify_emi()
        loan_line.view_process_values(self.journal_id,full_payment=True)
        self.loan_id.status = 'done'
        self.loan_id.message_post(body=f"<strong>Full Paid Amount:</strong> {loan_line.installment}")
