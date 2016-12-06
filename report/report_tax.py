# -*- coding: utf-8 -*-

import time
from openerp import models, fields, api, _
from openerp import api, models, exceptions

import logging
_logger = logging.getLogger(__name__)


class ReportTax(models.AbstractModel):
    _inherit = 'report.account_tax_report.report_tax_view'




    #get the base amount as per tax from account move line
    def _compute_base_amount_bal(self, tax_ids, data, company_id, out_refund = False):
        res = {}
        
        start_date = data['date_from']
        end_date = data['date_to']
        status = data['target_move']
        if status == 'all':
            state = ('draft', 'posted', )
        else:
            state = ('posted', )

        _logger.info("out_refund")
        _logger.info( out_refund )

        if start_date and end_date:
           
            self._cr.execute("""select \
                        SUM(""" + ( 'move_line.credit' if not out_refund else 'move_line.debit' ) + """) as base_amount,\
                        move_rel.account_tax_id as tax_id\
                    from \
                        account_move as move \
                    LEFT JOIN \
                        account_move_line move_line ON \
                        (move_line.move_id = move.id) \
                    LEFT JOIN \
                        account_move_line_account_tax_rel move_rel ON \
                        (move_rel.account_move_line_id = move_line.id) \
                    where \
                        move_line.date >= %s \
                        AND move_line.date <= %s\
                        AND move.id = move_line.move_id \
                        AND move_rel.account_tax_id in %s \
                        AND move_line.company_id = %s \
                        AND move.state in %s \
                    GROUP BY \
                        move_rel.account_tax_id \
                        """, ( start_date, end_date, tuple(tax_ids), company_id, state))
        else:
            self._cr.execute("""select \
                        SUM(""" + ( 'move_line.credit' if not out_refund else 'move_line.debit' ) + """) as base_amount ,\
                        move_rel.account_tax_id as tax_id\
                    from \
                        account_move as move \
                    LEFT JOIN \
                        account_move_line move_line ON \
                        (move_line.move_id = move.id) \
                    LEFT JOIN \
                        account_move_line_account_tax_rel move_rel ON \
                        (move_rel.account_move_line_id = move_line.id) \
                    where \
                        move_rel.account_tax_id in %s \
                        AND move_line.company_id = %s \
                        AND move.id = move_line.move_id \
                        AND move.state in %s \
                    GROUP BY \
                        move_rel.account_tax_id \
                        """, (tuple(tax_ids), company_id, state))
        
        result = self._cr.dictfetchall()
        return result
    
    #get the tax amount as per tax from account move line
    def _compute_tax_balance(self, tax_ids, data, out_refund = False):
        company_id = self.env.user.company_id.id
        res = {}
        
        #get the base amount for taxes
        base_amt_val = self._compute_base_amount_bal(tax_ids, data, company_id, out_refund)
        
        start_date = data['date_from']
        end_date = data['date_to']
        status = data['target_move']
        if status == 'all':
            state = ('draft', 'posted', )
        else:
            state = ('posted', )
            
        if start_date and end_date:

            #_logger.info("sql 1")
            #_logger.info( sql )

            self._cr.execute("""SELECT  \
                SUM(line.debit - line.credit) AS tax_amount ,\
                line.tax_line_id as tax_id\
            FROM account_move_line AS line, \
                account_move AS move \
            WHERE \
                line.tax_line_id in %s  \
                AND line.company_id = %s \
                AND move.id = line.move_id \
                AND line.date >=  %s \
                AND line.date <=  %s \
                AND move.state in %s \
                """+ ("AND move.id not in( select move_id from account_invoice where type = 'out_refund'  and move_id is not null )" if not out_refund 
                    else "AND move.id in( select move_id from account_invoice where type = 'out_refund'  and move_id is not null )" ) +"""                        
            GROUP BY \
                line.tax_line_id \
            """, (tuple(tax_ids),
                company_id, start_date, end_date, state) )
            
        else:
            self._cr.execute("""SELECT  \
                SUM(line.debit - line.credit) AS tax_amount ,\
                line.tax_line_id as tax_id\
            FROM account_move_line AS line, \
                account_move AS move \
            WHERE \
                line.tax_line_id in %s  \
                AND line.company_id = %s \
                AND move.id = line.move_id \
                AND move.state in %s \
                """+ ("AND move.id not in( select move_id from account_invoice where type = 'out_refund'  and move_id is not null )" if not out_refund 
                    else "AND move.id in( select move_id from account_invoice where type = 'out_refund'  and move_id is not null )" ) +"""
            GROUP BY \
                line.tax_line_id \
            """, (tuple(tax_ids),
                company_id, state) )

        result = self._cr.dictfetchall()

        for base_amt in base_amt_val:
            #_logger.info('base_amt**')
            #_logger.info(base_amt)

            for r in result:
                if r['tax_id'] == base_amt['tax_id']:
                    if r['tax_id'] not in res:
                        res[r['tax_id']] =  {'id': r['tax_id'], 'tax_amount': r['tax_amount'], 'base_amount':base_amt['base_amount']}

                        #_logger.info("res")
                        #_logger.info( res )

        #_logger.info("Ultimo")                
        #_logger.info(res)                
        return res



    #get the tax amount as per tax from account move line
    def _compute_tax_balance_detail(self, tax_ids, data, out_refund = False):
        company_id = self.env.user.company_id.id
        res = {}
        
        #get the base amount for taxes
        #base_amt_val = self._compute_base_amount_bal(tax_ids, data, company_id)
        
        start_date = data['date_from']
        end_date = data['date_to']
        status = data['target_move']
        if status == 'all':
            state = ('draft', 'posted', )
        else:
            state = ('posted', )
        if start_date and end_date:

            #_logger.info("La sql")
            


            self._cr.execute("""SELECT  \
                SUM(line.debit - line.credit) AS tax_amount ,\
                line.id as id ,\
                line.partner_id as partner_id ,\
                line.account_id as account_id ,\
                line.name as name ,\
                line.date as date ,\
                line.ref as ref ,\
                line.tax_line_id as tax_id \
            FROM account_move_line AS line, \
                account_move AS move \
            WHERE \
                line.tax_line_id in %s  \
                AND line.company_id = %s \
                AND move.id = line.move_id \
                AND line.date >=  %s \
                AND line.date <=  %s \
                AND move.state in %s \
                """+ ("AND move.id not in( select move_id from account_invoice where type = 'out_refund'  and move_id is not null )" if not out_refund 
                    else "AND move.id in( select move_id from account_invoice where type = 'out_refund'  and move_id is not null )" ) +"""
            GROUP BY \
                line.id, line.tax_line_id\
            """, (tuple(tax_ids),
                company_id, start_date, end_date, state))
             
        else:

            #_logger.info("La sql 2")


            self._cr.execute("""SELECT  \
                SUM(line.debit - line.credit) AS tax_amount ,\
                line.id as id ,\
                line.partner_id as partner_id ,\
                line.name as name ,\
                line.date as date ,\
                line.ref as ref ,\
                line.account_id as account_id ,\
                line.tax_line_id as tax_id\
            FROM account_move_line AS line, \
                account_move AS move \
            WHERE \
                line.tax_line_id in %s  \
                AND line.company_id = %s \
                AND move.id = line.move_id \
                AND move.state in %s \
                """+ ("AND move.id not in( select move_id from account_invoice where type = 'out_refund'  and move_id is not null )" if not out_refund 
                    else "AND move.id in( select move_id from account_invoice where type = 'out_refund'  and move_id is not null )" ) +"""
            GROUP BY \
                line.id, line.tax_line_id\
            """, (tuple(tax_ids),
                company_id, state))
            
        result = self._cr.dictfetchall()
        

        #_logger.info("El result")
        #_logger.info(result)

        return result

    def _compute_report_balance(self, reports, data, _out_refund = True):
        '''returns a dictionary with key=the ID of a record and value=the base amount and balance amount
           computed for this record. If the record is of type :
               'taxes' : it's the sum of the linked taxes
               'tax_type' : it's the sum of leaf tax with such an tax_type
               'tax_report' : it's the tax of the related report
               'sum' : it's the sum of the children of this record (aka a 'view' record)'''
        res = {}
        res_detail = {}
        fields = ['tax_amount', 'base_amount']
        add_fields = []
        company_id = self.env.user.company_id.id
        for report in reports:
            if _out_refund:
                out_refund = report.show_refound
            else:
                out_refund = True 



            if report.id in res:
                continue
            res[report.id] = dict((fn, 0.0) for fn in fields)
            
            if report.type == 'taxes':
                # it's the sum of the linked taxes
                if report.tax_ids:
                    res[report.id]['tax'] = self._compute_tax_balance(report.tax_ids.ids, data, out_refund)
                    if data['display_detail']:
                        for tax in report.tax_ids.ids:
                            res_detail[tax] = dict((fn, 0.0) for fn in add_fields)
                            res_detail[tax]['move'] = self._compute_tax_balance_detail([tax], data, out_refund)
                    for value in res[report.id]['tax'].values():
                        for field in fields:
                            res[report.id][field] += value.get(field)
            elif report.type == 'tax_type':
                # it's the sum the leaf taxes with such an tax type
                taxes = self.env['account.tax'].search([('tag_ids', 'in', report.tax_type_ids.ids), ('company_id', '=', company_id)])
                if taxes.ids:
                    res[report.id]['tax'] = self._compute_tax_balance(taxes.ids, data, out_refund)
                    for tax in taxes.ids:
                        res_detail[tax] = dict((fn, 0.0) for fn in add_fields)
                        res_detail[tax]['move'] = self._compute_tax_balance_detail([tax], data, out_refund)
                    for value in res[report.id]['tax'].values():
                        for field in fields:
                            res[report.id][field] += value.get(field)
            elif report.type == 'tax_report' and report.tax_report_id:
                # it's the amount of the linked report
                res2,res_detail = self._compute_report_balance(report.tax_report_id, data, out_refund)
                for key, value in res2.items():
                    for field in fields:
                        res[report.id][field] += value[field]
            elif report.type == 'sum':
                # it's the sum of the children of this taxes.report
                res2,res_detail = self._compute_report_balance(report.children_ids, data, out_refund)
                for key, value in res2.items():
                    for field in fields:
                        res[report.id][field] += value[field]
        return res,res_detail
    
    def get_tax_lines(self, data, out_refund = False):
        lines = []
        tax_report = self.env['taxes.report'].search([('id', '=', data['tax_report_id'][0])])
        #_logger.info("tax_report")
        #_logger.info(tax_report)

        child_reports = tax_report._get_children_by_order()
        #_logger.info("child_reports")
        #_logger.info(child_reports)

        company_id = self.env.user.company_id.id
        (res, res_detail) = self.with_context(data.get('used_context'))._compute_report_balance(child_reports, data, out_refund)
        
        for report in child_reports:
            #_logger.info( "report" )
            #_logger.info( report )
            if report.skip_display_base_amount:
                base_amount_show = 0.0
            else:
                base_amount_show = res[report.id]['base_amount'] * report.sign
            vals = {
                'name': report.name,
                'tax_amount': res[report.id]['tax_amount'] * report.sign,
                'type': 'report',
                'base_amount': base_amount_show,
                'level': bool(report.style_overwrite) and report.style_overwrite or report.level,
                'tax_type': report.type or False, #used to underline the financial report balances,
                'sign': report.sign,
            }
            #_logger.info("Los vals 1")        
            #_logger.info(vals)      

            lines.append(vals)
            if report.display_detail == 'no_detail':
                #the rest of the loop is used to display the details of the financial report, so it's not needed here.
                continue

            #_logger.info("Sigueeeeee")    

            if res[report.id].get('tax'):
                for tax_id, value in res[report.id]['tax'].items():
                    if report.skip_display_base_amount:
                        base_amount_show1 = False
                    else:
                        base_amount_show1 = value['base_amount'] * report.sign or 0.0
                    tax = self.env['account.tax'].browse(tax_id)
                    vals = {
                     'name': tax.name,
                     'tax_amount': value['tax_amount'] * report.sign or 0.0,
                     'base_amount': base_amount_show1,
                     'type': 'taxes',
                     'level': report.display_detail == 'detail_with_hierarchy' and 4,
                     'tax_type': tax.type_tax_use,
                     'sign': report.sign,
                     'detail': False
                        }
                    lines.append(vals)
                    #_logger.info("Los vals 2")        
                    #_logger.info(vals)      

                    if data['display_detail']:
                        for tax1 in res_detail[tax.id]['move']: 
                            move = self.env['account.move.line'].browse(tax1['id'])
                            account = self.env['account.account'].browse(tax1['account_id'])
                            partner = self.env['res.partner'].browse(tax1['partner_id'])
                            vals = {
                             'name': move.move_id.name,
                             'tax_amount': tax1['tax_amount'] * report.sign or 0.0,
                             'base_amount': base_amount_show1,
                             'type': 'taxes',
                             'level': report.display_detail == 'detail_with_hierarchy' and 5,
                             'tax_type': tax.type_tax_use,
                             'sign': report.sign,
                             'partnername': partner.name,
                             'account': account.name,
                             'detail': True,
                             'notes': ' ',
                            'date': tax1['date'],
                            'ref': tax1['ref'],
                                }
                            lines.append(vals)

                            #_logger.info("Los vals 3")        
                            #_logger.info(vals)        
                            
        return lines

    @api.multi
    def render_html(self, data):
        self.model = self.env.context.get('active_model')
        docs = self.env[self.model].browse(self.env.context.get('active_id'))
        
        _logger.info("El self")
        _logger.info( self )
        _logger.info( docs )

        report_lines = self.get_tax_lines(data.get('form'), True)
        report_lines_devoluciones = self.get_tax_lines(data.get('form'), False)

        _logger.info("report_lines")
        _logger.info(report_lines)

        docargs = {
            'doc_ids': self.ids,
            'doc_model': self.model,
            'data': data['form'],
            'docs': docs,
            'time': time,
            'get_tax_lines': report_lines,
            'get_tax_lines_devoluciones': report_lines_devoluciones,
        }
        return self.env['report'].render('account_tax_report.report_tax_view', docargs)
