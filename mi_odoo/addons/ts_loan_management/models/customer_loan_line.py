from odoo import fields, models, api, tools, exceptions, _
import math
from odoo.exceptions import ValidationError,UserError



class CustomerLoanLine(models.Model):
    _name = 'customer.loan.line'
    _description = 'Loan Installment'
    _inherit = ['mail.thread']
    _rec_name = 'loan_id'

    due_date = fields.Date(string='Due Date')
    interest = fields.Float('Interest')
    installment = fields.Float('Installment')
    loan_id = fields.Many2one('customer.loan', string='Loan Request', ondelete='cascade')
    acc_move_ids = fields.One2many('account.move','loan_line_id' )
    rate_month = fields.Float(string='Monthly Rate', digits=(16,7))
    paid_date = fields.Date(string='Paid Date', track_visibility='onchange')
    company_id = fields.Many2one('res.company', related='loan_id.company_id')
    currency_id = fields.Many2one('res.currency', related='loan_id.currency_id')
    partner_id = fields.Many2one('res.partner',related='loan_id.partner_id', string='Partner', store=True)
    
    sr_number = fields.Integer(string='Sequence')
    remaining = fields.Float(string='Remaining Principal')
    paid = fields.Float(string='Total Paid Amount')
    hide_payment_btn = fields.Boolean(string='Hide Payment Amount', compute='compute_invisible_payment_amount')
    rate = fields.Float(string='Total Rate', compute='_calculate_main_rate')
    amount = fields.Float('Principal', compute='_compute_installment')
    status = fields.Selection([('draft', 'Draft'),('cancel', 'Cancelled'), ('paid', 'Paid')], string='Status',default='draft', track_visibility='onchange')

    def mark_unpaid(self):
        self.ensure_one()
        if self.loan_id.status != 'done':
            if self.status == 'paid':
                entries = self.acc_move_ids
                for entry in entries:
                    entry.button_draft()
                    entry.button_cancel()
                self.write({'status':'draft'})
                self.loan_id.message_post(body=f"<strong>EMI Marked Unpaid. Amount:</strong> {self.installment}")
        else:
            raise UserError('Cannot mark an EMI "Unpaid" when Loan is Done')


    def _calculate_main_rate(self):
        for rec in self:
            rec.rate = rec.rate_month*1200

    def _compute_installment(self):
        for rec in self:
            if rec.installment:
                rec.amount = abs(rec.installment - rec.interest)
   
    def check_move_amount(self):      
        self.ensure_one()
        interest_moves = self.acc_move_ids.mapped('line_ids').filtered(lambda r: r.account_id == self.loan_id.credit_account_id)
        principal_moves = self.acc_move_ids.mapped('line_ids').filtered(lambda r: r.account_id == self.loan_id.debit_account_id)
        self.interest = (sum(interest_moves.mapped('credit')) - sum(interest_moves.mapped('debit')))
        self.installment = (sum(principal_moves.mapped('debit')))

    def move_vals(self,journal,full_payment):
        move_ref = str(self.loan_id.name) + ' ' + str(self.loan_id.partner_id.name)
        return {
            'loan_line_id': self.id,
            'loan_id': self.loan_id.id,
            'date': self.due_date,
            'ref': move_ref,
            'journal_id': journal.id, 
            'line_ids': [(0, 0, vals) for vals in self.move_line_vals(full_payment)],
            'partner_id':self.loan_id.partner_id.id,
            'narration': str(self.loan_id.partner_id.name) +' ' + str(self.loan_id.name) +' ' + str(self.sr_number)
            }

    def move_line_vals(self,full_payment):
        vals = []
        partner = self.loan_id.partner_id.with_context(with_company=self.loan_id.company_id.id)

        vals.append({
            'account_id': self.loan_id.emi_credit_account_id.id, 
            'debit': 0, 
            'credit': self.installment - self.interest,
            'partner_id': partner.id,
            'name':str(self.loan_id.name) + ' ' + str(self.partner_id.name) + ' EMI ' + str(self.sr_number) + ' Priniciple Debit' if not full_payment else str(self.loan_id.name) + ' ' + str(self.partner_id.name) + ' Priniciple Full Debit'
        })
        
        vals.append({
            'account_id': self.loan_id.credit_account_id.id, 
            'debit': self.installment - self.interest, 
            'credit': 0,
            'partner_id': partner.id,
            'name':str(self.loan_id.name) + ' ' + str(self.partner_id.name) + ' EMI ' + str(self.sr_number) + ' Principle Credit'  if not full_payment else str(self.loan_id.name) + ' ' + str(self.partner_id.name) + ' Priniciple Full Credit'
        })
        
        vals.append({
            'account_id': self.loan_id.credit_account_id.id, 
            'debit': 0, 
            'credit': self.interest,
            'partner_id': partner.id,
            'name':str(self.loan_id.name) + ' ' + str(self.partner_id.name) + ' EMI ' + str(self.sr_number) + ' Interest Booked' if not full_payment else str(self.loan_id.name) + ' ' + str(self.partner_id.name) + ' Interest Booked'
        })
        
        vals.append({
            'account_id': self.loan_id.interest_account_id.id, 
            'debit': self.interest, 
            'credit': 0,
            'partner_id': partner.id,
            'name':str(self.loan_id.name) + ' ' + str(self.partner_id.name) + ' EMI ' + str(self.sr_number) + ' Interest Expense Booked' if not full_payment else str(self.loan_id.name) + ' ' + str(self.partner_id.name) + ' Interest Expense Booked'
        })
        
        vals.append({
            'account_id': self.loan_id.emi_credit_account_id.id, 
            'debit': 0, 
            'credit': self.interest,
            # Added by Technians
            'partner_id': partner.id, 
            'name':str(self.loan_id.name) + ' ' + str(self.partner_id.name) + ' EMI ' + str(self.sr_number) + ' Interest Debit' if not full_payment else str(self.loan_id.name) + ' ' + str(self.partner_id.name) + ' Interest Debit'
        })
        
        vals.append({
            'account_id': self.loan_id.credit_account_id.id, 
            'debit': self.interest, 
            'credit': 0,
            # Added by Technians
            'partner_id': partner.id, 
            'name':str(self.loan_id.name) + ' ' + str(self.partner_id.name) + ' EMI ' + str(self.sr_number) + ' Interest Credit' if not full_payment else str(self.loan_id.name) + ' ' + str(self.partner_id.name) + ' Interest Credit'
        })
        

        return vals

    def view_process_values(self,journal,full_payment=False):
        
        res = []
        move_obj = self.env['account.move']
        for record in self:
            if not record.acc_move_ids:
                if record.loan_id.line_ids.filtered(lambda r: r.due_date < record.due_date and not r.acc_move_ids):
                    raise exceptions.UserError(_("Please Pay Remaining Installments First."))
                # raise ValidationError(str(record.move_vals(journal)))
                move = move_obj.create(record.move_vals(journal,full_payment))
                
                move.action_post()
                
                res.append(move.id)
        
        action = self.env.ref('account.action_move_line_form').read()[0]
       
        action['context'] = {'default_loan_line_id': self.id,'default_loan_id': self.loan_id.id }
        action['domain'] = [('loan_line_id', '=', self.id)]
        if len(self.acc_move_ids) == 1:
            res = self.env.ref('account.move.form', False)
            action['views'] = [(res and res.id or False, 'form')]
            action['res_id'] = self.acc_move_ids.id

        return action

    @api.depends('status','loan_id.status','installment')
    def compute_invisible_payment_amount(self):
        for rec in self:
            flag = False
            if rec.status == 'draft' and tools.float_round(rec.installment, 2) > 0.0 and rec.loan_id.status == 'approved':
                flag = True
            else:
                flag = False
            rec.hide_payment_btn = flag
