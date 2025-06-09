from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CustomerLoanPayAmount(models.TransientModel):
    _name = 'customer.loan.pay.amount'
    _description = 'Loan Pay Amount'

    @api.constrains('date')
    def check_cost_estimation(self):
        if self.date < self.loan_id.start_date:
            raise UserError('You cannot set date before loan start date')

    loan_line_id = fields.Many2one('customer.loan.line', string="Loan Line")
    loan_id = fields.Many2one('customer.loan', related='loan_line_id.loan_id')
    currency_id = fields.Many2one('res.currency',related='loan_id.currency_id',readonly=True )
    date = fields.Date()
    amount = fields.Monetary( currency_field='currency_id', string='Principal Amount' )
    interest = fields.Monetary(currency_field='currency_id', string='Interests')
    total_amount = fields.Monetary( currency_field='currency_id', string='Total',compute='compute_total_amount')
    journal_id = fields.Many2one('account.journal', string='Journal')

    @api.depends('amount','interest')
    def compute_total_amount(self):
        for rec in self:
            self.total_amount = self.amount + self.interest

    @api.onchange('loan_line_id')
    def onchange_loan_line_id(self):
        if self.loan_line_id:
            self.update({'date': self.loan_line_id.due_date,
                        'amount': self.loan_line_id.amount,
                        'interest': self.loan_line_id.interest,
                        'journal_id': self.loan_line_id.loan_id.loan_journal_id.id})
        return

    def pay_amount(self):
        self.loan_line_id.view_process_values(self.journal_id)
        if self.date:
            self.loan_line_id.due_date = self.date
        self.loan_line_id.status = 'paid'
        self.loan_id.message_post(body=f"<strong>EMI Paid Amount:</strong> {self.loan_line_id.installment}")

