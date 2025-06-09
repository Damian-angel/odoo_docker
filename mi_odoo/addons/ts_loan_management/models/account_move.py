# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    loan_line_id = fields.Many2one('customer.loan.line', ondelete='restrict')
    loan_id = fields.Many2one('customer.loan', store=True,ondelete='restrict')

    def post(self):
        res = super(AccountMove, self).post()
        for record in self:
            if record.loan_line_id:
                record.loan_id = record.loan_line_id.loan_id
                if record.loan_line_id.sr_number == record.loan_id.no_of_installment:
                    record.loan_id.status = 'done'
        return res
