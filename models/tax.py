# -*- coding: utf-8 -*-

from openerp import api, models, fields, _
from openerp import SUPERUSER_ID
class TaxesReport(models.Model):
    _inherit = 'taxes.report'
    
    show_refound = fields.Boolean('Show Refound')