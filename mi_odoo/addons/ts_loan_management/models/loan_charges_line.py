from odoo import fields, models, api
from odoo.exceptions import ValidationError
import math

class DeleteLoanChargesLine(models.TransientModel):
    _name = 'delete.loan.charges.line'

    name = fields.Many2one('loan.charges.line.technians',string='Charge', create=False, edit=False)

    def delete_loan_charges(self):
        journal_entry = int(self.name.journal_entries)
        if journal_entry:
            account_move = self.env['account.move'].search([('id','=',journal_entry)],limit=1)
            if account_move:
                account_move.button_draft()
                account_move.button_cancel()
                self.name.loan_id.message_post(body=f"<strong>Loan Charge Deleted. Amount:</strong> {self.name.amount}")
                self.name.unlink()
        else:
            self.name.unlink()


class LoanChargesLine(models.Model):
    _name = 'loan.charges.line.technians'
    _description = 'Loan Charges line'
    

    @api.depends('amount_untaxed', 'tax_id')
    def compute_tax_amount(self):
        for rec in self:
            if rec.amount_untaxed:
                final_amount = rec.amount_untaxed
                tax_amount = 0.0
                if rec.tax_id:
                    tax_amount += (rec.amount_untaxed * rec.tax_id.amount) / 100
                rec.amount = final_amount + tax_amount
                rec.amount_tax = tax_amount
            else:
                rec.amount = 0.0
                rec.amount_tax = 0.0

    name = fields.Char(string="Description")
    loan_id = fields.Many2one('customer.loan',string="Loan")
    loan_charges_id = fields.Many2one('loan.charges.technians',string="Charges")
    tax_id = fields.Many2one('account.tax',string="Tax")
    # tax_id_domain = fields.Char('Tax Domain',compute=_compute_tax_domain)
    journal_id = fields.Many2one('account.journal',string="Journal")
    journal_entries = fields.Char('Journal Entries')
    account_id = fields.Many2one('account.account',string="Account")
    account_entries = fields.Char('Account Entries')
    charge_amount_type = fields.Selection([('fixed','Fixed'),('percent','Percent')],default='fixed',string="Charge Type")
    charge_amount = fields.Float('Charge Amount')
    
    amount_untaxed = fields.Float('Untaxed')
    amount_tax = fields.Float('Tax Amount',compute=compute_tax_amount)
    amount = fields.Float('Amount',compute=compute_tax_amount)

    debit_account_id = fields.Many2one('account.account',string='Debit Account')
    date = fields.Date(string='Date')

    invoice = fields.Char(string='Invoice No.')

    @api.onchange('charge_amount','charge_amount_type')
    def onchange_charge_amount(self):
        charge_amount_type = self.charge_amount_type
        charge_amount = self.charge_amount
        loan_amount = self.loan_id.amount
        final_amount = ''
        if(charge_amount_type == 'percent' and charge_amount > 100):
             raise ValidationError("Percentage should not exceed 100")
        else:
            
            if(charge_amount_type == 'percent' and charge_amount):
                final_amount = (loan_amount * charge_amount)/100
            if(charge_amount_type == 'fixed' and charge_amount):
                final_amount = charge_amount
            self.amount_untaxed = final_amount
            
    @api.onchange('loan_charges_id')
    def onchange_loan_charges(self):
        if self.loan_charges_id:
            charge_amount = self.loan_charges_id.charge_amount
            charge_amount_type = self.loan_charges_id.charge_amount_type
            loan_amount = self.loan_id.amount
            if loan_amount and charge_amount_type == 'percent':
                final_amount = (loan_amount * charge_amount)/100
            else:
                final_amount = charge_amount
            self.name = str(self.loan_charges_id.description or '') + ' ' + str(self.loan_id.partner_id.name) + ' ' + str(self.loan_id.name)
            self.tax_id = self.loan_charges_id.charge_tax_id
            self.charge_amount_type = self.loan_charges_id.charge_amount_type
            self.charge_amount = self.loan_charges_id.charge_amount
            self.journal_id = self.loan_charges_id.charge_journal_id
            self.account_id = self.loan_charges_id.charge_account_id
            self.amount = final_amount

    def action_open_journal_entries(self):
        return {
                    'name': 'Journal Entries',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_model': 'account.move',
                    'context': "{'type': 'out_invoice'}",
                    'type': 'ir.actions.act_window',
                    'nodestroy': True,
                    'target': 'current',
                    'res_id': int(self.journal_entries) or False,
                   }

    def delete_charges_wizard(self):
        self.ensure_one()
        context = {
            'default_name': self.id
        }
        return {
            'name': "Delete Charges and its journal Entries",
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'delete.loan.charges.line',
            'target': 'new',
            'context': context,
        }



class AccountTax(models.Model):
    _inherit = 'account.tax'

    def compute_taxes_on_charges(self,child,loan):
       
        # Retrieve tax records based on the provided tax IDs
        tax = self.env['account.tax'].browse(self.id)
        journal_entries = []
        if tax.amount_type == 'percent':
            repartition_lines = tax.invoice_repartition_line_ids
            for repartition_line in repartition_lines:
                if repartition_line.repartition_type == 'tax':
                    factor_percent = repartition_line.factor_percent
                    tax_amount = child.amount_untaxed * (tax.amount/100) * (factor_percent/100)
                    journal_entries += [(0, 0, {               
                            'name': str(child.loan_charges_id.name) + ' ' + str(tax.name) + ' ' + str(loan.name) + ' ' + 'Taxes',
                            'account_id': loan.debit_account_id.id,
                            'debit': 0,
                            'credit': round(tax_amount),
                        })]
                    journal_entries += [(0, 0, {               
                            'name': str(child.loan_charges_id.name) + ' ' + str(tax.name) + ' ' + str(loan.name) + ' ' + 'Taxes',
                            'account_id': repartition_line.account_id.id,
                            'debit': round(tax_amount),
                            'credit': 0,
                        })]

        elif tax.amount_type == 'group':
            group_taxes = tax.children_tax_ids
            for child_tax in group_taxes:
                journal_entries += child_tax.compute_taxes_on_charges(child,loan)
        
        else:
            raise ValidationError('Operation valid for Tax types percent and group');
        
        return journal_entries
