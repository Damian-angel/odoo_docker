from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from odoo import fields, models, api, exceptions, tools, _
import math
import numpy_financial as npf
from odoo.exceptions import ValidationError, UserError


class CustomerLoan(models.Model):
    _name = 'customer.loan'
    _inherit = ['mail.thread']
    _description = 'Customer Loan'

    @api.depends('line_ids')
    def compute_installment_payment(self):
        for rec in self:
            total_paid_installment = 0.00
            paid_interest = 0.00
            for inst_line in rec.line_ids:
                if inst_line.status in ['paid', 'cancel']:
                    total_paid_installment += inst_line.amount
                    paid_interest += inst_line.interest
            rec.total_paid = total_paid_installment
            rec.total_paid_interest = paid_interest
            rec.total_remaining = abs(rec.amount - total_paid_installment)

    # Added by Technians
    # loan_type = fields.Selection([('customer_loan','Customer Loan'),('vendor_loan','Vendor Loan')])
    loan_type = fields.Selection([('customer', 'Customer Loan'), ('supplier', 'Vendor Loan')])
    partner_id = fields.Many2one('res.partner', 'Partner')
    total_paid_interest = fields.Float(compute='compute_installment_payment', string='Total Paid Interest')

    customer_id = fields.Many2one('res.partner', 'Customer')
    acc_acc_move_ids = fields.One2many('account.move', 'loan_id', copy=False)
    vendor_id = fields.Many2one('res.partner', 'Vendor')
    hide_cancel_reason = fields.Boolean(string='Hide Cancel Reason?', compute='check_interval_in_loan')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.user.company_id, string='Company')
    amount = fields.Float('Loan Amount')
    no_of_installment = fields.Integer('No. of Installments', help='How Many Installments?')
    payment_method = fields.Selection([('cash', 'Cash'), ('bank', 'Bank')], string='Payment Method')
    total_paid = fields.Float(compute='compute_installment_payment', string='Total Paid Principle')
    total_remaining = fields.Float(compute='compute_installment_payment', string='Total Remaining Principle')
    debit_account_id = fields.Many2one('account.account', string='Debit Account')
    credit_account_id = fields.Many2one('account.account', string='Credit Account')
    emi_credit_account_id = fields.Many2one('account.account', string='EMI Account')
    interest_account_id = fields.Many2one('account.account', string='Interest Account')
    loan_issuing_date = fields.Date(string='Installment Start From')
    start_date = fields.Date(string='Installment Start Date', default=datetime.today(), copy=False)
    accounting_date = fields.Date(string='Accounting Date')
    description = fields.Text('Terms & Condition')
    line_ids = fields.One2many('customer.loan.line', 'loan_id')
    loan_journal_id = fields.Many2one('account.journal', string='Journal')
    loan_approve_date = fields.Date(string='Approved Date')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.user.company_id.currency_id.id)
    number_of_interval = fields.Integer(string='Interval', default='1')
    select_period = fields.Selection([('days', 'Days'), ('months', 'Months'), ('years', 'Years')], default='months',
                                     string='Period')
    rate = fields.Float(help='Currently applied rate')
    rate_period = fields.Float(compute='_compute_rate_period', digits=(16, 7))
    name = fields.Char(string="Name", default='New', copy=False)
    hide_interval = fields.Boolean(string='Hide Interval', compute='check_interval_in_loan')
    # process_fee = fields.Float('Processing Fee')
    user_id = fields.Many2one('res.users', 'Sales Person', default=lambda self: self._uid)
    status = fields.Selection(
        [('draft', 'To Request'), ('waiting', 'Waiting For Approval'), ('approved', 'Confirm'), ('cancel', 'Cancelled'),
         ('done', 'Done')], default='draft', string='Status', copy=False)

    # Added by Technians
    loan_charges_ids = fields.One2many('loan.charges.line.technians', inverse_name="loan_id", string="Charges")
    show_charges_button = fields.Boolean(string='Show Button', compute='_compute_show_button')

    charge_account_id = fields.Many2one('account.account', string='Charge Account')
    loan_disperse_date = fields.Date(string='Loan Disperse Date')
    disbursement_amount = fields.Float('Disbursement amount', compute='_compute_disbursement_amount')

    active = fields.Boolean(default=True)
    loan_account_no = fields.Char(string='Loan Account No')

    def write(self, vals):
        if vals.get('status') and vals.get('status') == 'done':
            self.active = False
        return super(CustomerLoan, self).write(vals)

    @api.depends('amount', 'loan_charges_ids')
    def _compute_disbursement_amount(self):
        for loan in self:
            total_charge = 0.0
            for charge in loan.loan_charges_ids:
                if not charge.loan_charges_id.is_foreclosure:
                    total_charge += charge.amount
            loan.disbursement_amount = loan.amount - total_charge

    @api.depends('loan_charges_ids.journal_entries')  # Replace 'entry_field' with the actual field name in charges
    def _compute_show_button(self):
        for loan in self:
            # Check if any of the related charges records have a blank or False value
            if loan.status == 'approved':
                show_button = any(not charge_line.journal_entries for charge_line in loan.loan_charges_ids)
                loan.show_charges_button = show_button
            else:
                loan.show_charges_button = False


    @api.onchange('loan_type')
    def _onchange_loan_type(self):
        if self.loan_type == 'supplier':
            return {'domain': {'partner_id': [('supplier_rank', '>', 0)]}}
        elif self.loan_type == 'customer':
            return {'domain': {'partner_id': [('customer_rank', '>', 0)]}}
        else:
            return {'domain': {'partner_id': []}}

    @api.depends('company_id')
    def check_interval_in_loan(self):
        for rec in self:
            if rec.company_id.interval_in_loan:
                rec.hide_interval = True
            else:
                rec.hide_interval = False

    @api.constrains('rate', 'amount', 'no_of_installment')
    def _check_amount(self):
        if self.amount <= 0.00:
            raise exceptions.UserError(_("Please Enter Valid Loan Amount"))

        if self.rate < 0.0:
            raise exceptions.UserError(_("Please Enter Greater Than Zero Rate"))

        if self.no_of_installment <= 0:
            raise exceptions.UserError(_("Please Enter Valid value for Number of Installment"))

    @api.depends('rate')
    def _compute_rate_period(self):
        for rec in self:
            rec.rate_period = (rec.rate / 12) / 100

    def view_entry(self):
        action = self.env.ref('account.action_move_line_form').read()[0]
        action['domain'] = [('loan_id', '=', self.id)]

        return action

    def view_items(self):
        entry_ids = self.env['account.move'].search([('loan_id', '=', self.id)]).ids
        #    raise exceptions.ValidationError(entry_ids)
        action = self.env.ref('account.action_move_line_select').read()[0]
        action['domain'] = [('move_id', 'in', entry_ids)]
        action['context'] = [('search_default_posted', '=', True)]
        return action

    def action_reset_todraft(self):
        self.write({'status': 'draft'})
        return True

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            if 'company_id' in vals:
                vals['name'] = self.env['ir.sequence'].with_context(force_company=vals['company_id']).next_by_code(
                    'customer.loan') or _('New')
            else:
                vals['name'] = self.env['ir.sequence'].next_by_code('customer.loan') or _('New')
        return super(CustomerLoan, self).create(vals)

    def unlink(self):
        for rec in self:
            rec.delete_loan_entries()
            # if rec.status != 'draft':
            #     raise exceptions.UserError(_('You cannot Remove Customer Loan.'))
        return super(CustomerLoan, self).unlink()

    def button_to_unlink(self):
        loan_ids = self._context.get('active_ids', [])
        ctx = {
            'default_loan_ids': [(6, 0, loan_ids)]
        }
        return {
            'type': 'ir.actions.act_window',
            'name': 'Confirmation',
            'res_model': 'delete.loan.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('ts_loan_management.form_view_of_loan_delete_loan').id,
            'target': 'new',
            'context': ctx
        }

    def delete_loan_entries(self):
        self.ensure_one()
        journal_entries = self.acc_acc_move_ids
        for journal_entry in journal_entries:
            journal_entry.button_draft()
            journal_entry.button_cancel()

    def revert_disbursement(self):
        self.delete_loan_entries()
        self.action_reset_todraft()
        emis = self.env['customer.loan.line'].search([('loan_id', '=', self.id)])
        for emi in emis:
            emi.mark_unpaid()
        charges = self.env['loan.charges.line.technians'].search([('loan_id', '=', self.id)])
        for charge in charges:
            amount = charge.amount
            charge.unlink()
            self.message_post(body=f"<strong>Loan Charge Deleted. Amount:</strong> {amount}")
        self.message_post(body=f"<strong>Loan Disbursement Reverted. Amount:</strong> {self.disbursement_amount}")

    def action_send_approval(self):
        for rec in self:
            rec.status = 'waiting'

    def approve_loan(self):
        if not self.line_ids:
            self.action_calculation()
        self.write({'status': 'approved', 'accounting_date': datetime.now(), 'loan_approve_date': datetime.now()})
        self.create_accounting_entry()
        self.message_post(body=f"<strong>Loan Disbursement Amount:</strong> {self.disbursement_amount}")

    def action_cancel(self):
        journal_entries = self.env['account.move'].search([('loan_id', '=', self.id)])
        if not journal_entries.ids:
            self.status = 'cancel'
            self.line_ids.write({'status': 'cancel'})
        else:
            raise exceptions.UserError("You cannot cancel Loan after Journal Entries Posted.")

    def action_calculation(self):
        loan_list = []
        if any(state == 'paid' for state in self.line_ids.mapped('status')):
            raise ValidationError("You can't change calculation after installment paid.")
        for rec in self:
            amount = rec.amount
            no_of_installment = rec.no_of_installment
            if amount and no_of_installment:
                amount = amount / no_of_installment
                remaining = rec.amount
                interest = 0
                total_amount = 0.0
                loan_date = self.start_date
                du_date = 0
                # create installment
                for duration in range(0, no_of_installment):
                    interval = rec.number_of_interval * duration
                    if rec.select_period == 'days':
                        due_date = loan_date + relativedelta(days=interval)
                    elif rec.select_period == 'years':
                        due_date = loan_date + relativedelta(years=interval)
                    else:
                        due_date = loan_date + relativedelta(months=interval)
                    amt = -(npf.pmt(rec.rate_period, no_of_installment - duration, remaining))
                    interest = remaining * rec.rate_period
                    remaining = abs(remaining - tools.float_round(amt - interest, 2))
                    vals = {
                        'sr_number': duration + 1,
                        'status': 'draft',
                        'due_date': due_date,
                        'remaining': round(remaining),
                        'interest': round(interest),
                        'rate_month': rec.rate_period,
                        'loan_id': rec.id,
                        'installment': round(amt)
                    }
                    total_amount += tools.float_round(amount, 2)
                    loan_list.append((0, 0, vals))
                last_amount = amount - total_amount
                # last installment adding for solve rounding issues
                if last_amount != 0:
                    loan_list[-1][2]['amount'] = round(loan_list[-1][2].get('installment') + last_amount)
                # To remove duplicate lines
            for installment_rec in self.line_ids:
                loan_list.append((2, installment_rec.id))
            self.line_ids = loan_list

    def clear_installment_line(self):
        if any(state == 'paid' for state in self.line_ids.mapped('status')):
            raise exceptions.UserError("You can't clear lines after installment paid.")
        self.line_ids = False
        self.write({'line_ids': [(2, self.line_ids.ids)]})

    def create_accounting_entry(self):
        move_vals = []
        move_ref = str(self.name) + ' ' + str(self.partner_id.name)
        move = self.env['account.move'].create({
            'journal_id': self.loan_journal_id.id,
            'company_id': self.company_id.id,
            'date': self.loan_disperse_date,
            'ref': move_ref,
            'partner_id': self.partner_id.id,
            'name': '/',
            'narration': 'From - ' + move_ref
        })
        if move:
            vals = {
                'name': move_ref,
                'company_id': self.company_id.id,
                'currency_id': self.company_id.currency_id.id,
                'date_maturity': self.loan_issuing_date,
                'journal_id': self.loan_journal_id.id,
                'date': self.loan_disperse_date,
                # 'partner_id': self.customer_id.id,
                'partner_id': self.partner_id.id,
                'quantity': 1, 'move_id': move.id
            }

            debit_vals = {'account_id': self.debit_account_id.id, 'debit': self.amount, 'credit': 0.0}
            credit_vals = {'account_id': self.credit_account_id.id, 'credit': self.amount, 'debit': 0.0}
            debit_vals.update(vals)
            credit_vals.update(vals)
            move_vals.append((0, 0, debit_vals))
            move_vals.append((0, 0, credit_vals))
            move.line_ids = move_vals or False
            move.loan_id = self.id
            move.action_post()

    def action_open_journal_entries(self):
        action = self.env('account.action_move_line_form').read()[0]
        action['domain'] = [('ref', 'in', self.name)]
        return action

    def compute_posted_lines(self):
        amount = self.amount
        for line in self.line_ids.sorted('sr_number'):
            if line.acc_move_ids:
                amount = line.paid_amount
            else:
                line.interest = line.remaining_amount * line.rate_month
                if line.sr_number == line.loan_id.no_of_installment:
                    line.total_amount = line.amount + line.interest
                else:
                    line.total_amount = - npf.pmt(line.rate_month, line.loan_id.no_of_installment - line.sr_number + 1,
                                                  line.remaining_amount)
                amount -= line.total_amount - line.inter

    def action_create_journal_entry(self):
        for record in self:
            for child in record.loan_charges_ids:
                AccountMove = child.env['account.move']
                if not child.journal_entries:
                    charge_name = (child.name or 'Unnamed') + ' Charges'

                    journal_entry_line_ids = [(0, 0, {
                        'name': charge_name,
                        'account_id': self.debit_account_id.id,
                        'debit': 0,
                        'credit': round(child.amount_untaxed),
                    }), (0, 0, {
                        'name': charge_name,
                        'account_id': child.account_id.id,
                        'debit': round(child.amount_untaxed),
                        'credit': 0,
                    })

                                              ]
                    amount = self.amount

                    if child.tax_id:
                        tax = self.env['account.tax'].browse(child.tax_id.id)
                        tax_amount = child.tax_id.compute_taxes_on_charges(child, self)
                        # tax_amount = tax.amount
                        journal_entry_line_ids += tax_amount

                    narration = str(record.name) + ' ' + str(record.partner_id.name)
                    move_ref = str(self.name) + ' ' + str(self.partner_id.name)
                    journal_entry_data = {
                        'journal_id': child.journal_id.id,
                        'loan_id': self.id,
                        'ref': move_ref,
                        # 'partner_id':self.customer_id.id or self.vendor_id.id,
                        'partner_id': self.partner_id.id,
                        'line_ids': journal_entry_line_ids,
                        'narration': 'From - ' + str(narration),
                        'date': child.date,
                    }
                    # print('oooooooooooooooooooooooo',child.date)
                    # journal_entry_data['line_ids'].append(additional_line_item)
                    journal_entry = AccountMove.create(journal_entry_data)

                    # Confirm the journal entry
                    journal_entry.action_post()
                    record.message_post(body=f"<strong>Charge Created: </strong> {child.amount}")
                    child.journal_entries = journal_entry.id


class DeleteLoanWizard(models.TransientModel):
    _name = "delete.loan.wizard"

    loan_ids = fields.Many2many(comodel_name='customer.loan')

    def btn_ok(self):
        for loan_id in self.loan_ids:
            loan_id.sudo().unlink()
