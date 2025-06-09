# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    interval_in_loan = fields.Boolean(string='Interval in Installment')

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res.update(
            interval_in_loan = self.env.user.company_id.interval_in_loan
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        company_id=self.env.user.company_id
        company_id.interval_in_loan = self.interval_in_loan
