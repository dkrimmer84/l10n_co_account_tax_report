from odoo import api, models, fields, _
from odoo import SUPERUSER_ID


class TaxesReport(models.Model):
    _inherit = 'taxes.report'

    show_refound = fields.Boolean('Show Refound')

    def _get_children_by_order(self):
        '''returns a recordset of all the children computed recursively, and sorted by sequence. Ready for the printing'''
        res = self
        children = self.search([('parent_id', 'in', self.ids)], order='sequence ASC')
        if children:
            res += children._get_children_by_order()

        #_logger.info("testttt")
        #_logger.info(res)

        result = {}
        for rec in res:
            result[rec.sequence] = rec


        #_logger.info("result")
        #_logger.info(result)

        sorted_list = sorted(result.iteritems(), key=lambda key_value: key_value[0])

        #_logger.info("sorted_list")
        #_logger.info( sorted_list )

        final_res = self
        for s in sorted_list:
            if s[ 1 ] not in final_res:
                final_res += s[ 1 ]

        return final_res

