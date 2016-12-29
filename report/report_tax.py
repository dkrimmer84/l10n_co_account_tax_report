# -*- coding: utf-8 -*-

import time
from openerp import models, fields, api, _
from openerp import api, models, exceptions

import logging
_logger = logging.getLogger(__name__)



class ReportTax(models.AbstractModel):
	_inherit = 'report.account_tax_report.report_tax_view'
	#get the base amount as per tax from account move line
	def _compute_base_amount_bal(self, tax_ids, data, company_id, out_refund = False, report_sign = False):
		res = {}
		
		start_date = data['date_from']
		end_date = data['date_to']
		status = data['target_move']
		if status == 'all':
			state = ('draft', 'posted', 'paid')
		else:
			state = ('posted', )
		_sum_condition = self.sum_condition( tax_ids, out_refund, 'total' )
		
		if start_date and end_date:            

			self._cr.execute("""select \
						SUM(""" + _sum_condition + """) * """+ str(report_sign) +""" as base_amount,\
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
						SUM(""" + _sum_condition + """)   * """+ str(report_sign) +""" as base_amount ,\
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


		if start_date and end_date:  

			# Tax in invoice - Pos order
			self.env.cr.execute( """
			select polct.tax_id, sum(pol.price_unit * pol.qty) as base_amount
			from pos_order po, pos_order_line pol, pos_order_line_company_tax polct
			where 
			po.id = pol.order_id
			and polct.order_id = po.id
			and polct.tax_id  in( select id from account_tax where tax_in_invoice = true )
			and po.account_move in ( select am.id from account_move am where am.date >= %s and am.date <= %s and am.state in %s  )
			group by polct.tax_id
			""", ( start_date, end_date, state  ) )

			result2 = self.env.cr.dictfetchall()

			# Tax in invoice - Invoice
			self.env.cr.execute("""
			select ait.tax_id, sum(ail.price_unit * ail.quantity) as base_amount
			from account_invoice ai, account_invoice_line ail, account_invoice_tax ait
			where 
			ai.id = ail.invoice_id
			and ait.invoice_id = ai.id
			and ai.move_id in ( select am.id from account_move am where am.date >= %s and am.date <= %s and am.state in %s  )
			group by ait.tax_id
			""", ( start_date, end_date, state  ) )

			result3 = self.env.cr.dictfetchall()

			
			tax_id_amount = {}

			for tax in result2:

				tax_id_amount.update({
					'tax_id' : tax.get('tax_id'),
					'base_amount' : tax.get('base_amount') + tax_id_amount.get( tax.get('tax_id'), 0 )
				})

			for tax in result3:	

				tax_id_amount.update({
					'tax_id' : tax.get('tax_id'),
					'base_amount' : tax.get('base_amount') + tax_id_amount.get( tax.get('tax_id'), 0 )
				})

			_logger.info("result444444444")
			_logger.info( tax_id_amount )
			result4 = [ tax_id_amount ]

			"""_logger.info("result2")
			_logger.info(result2)

			_logger.info("result3")
			_logger.info(result3)

			_logger.info("result4")
			_logger.info(result4)"""


			result = result + result4

		else:
			pass		

		return result

	def type_tax_use( self, tax_ids ):
		account_tax_model = self.env['account.tax']
		account_tax_id = account_tax_model.search([('id', '=', tax_ids[ 0 ])])

		if account_tax_id:
			return account_tax_id.type_tax_use

		return False

	def sum_condition(self, tax_ids, out_refund, use = 'detail'):

		_type_tax_use = self.type_tax_use( tax_ids )
	   
		sum_condition = False
		if not out_refund:
			sum_condition = 'credit' if _type_tax_use == 'sale' else 'debit'
		else:
			sum_condition = 'debit' if _type_tax_use == 'sale' else 'credit'

		"""if not out_refund:
			sum_condition = 'debit' if _type_tax_use == 'sale' else 'credit'
		else:
			sum_condition = 'credit' if _type_tax_use == 'sale' else 'debit'"""

		if use == 'total':
			sum_condition = 'move_line.' + sum_condition 
		else:
			sum_condition = 'line.' + sum_condition 


		return sum_condition 
	#get the tax amount as per tax from account move line
	def _compute_tax_balance(self, tax_ids, data, out_refund = False, report_sign = False):
		company_id = self.env.user.company_id.id
		res = {}
		

		#get the base amount for taxes
		base_amt_val = self._compute_base_amount_bal(tax_ids, data, company_id, out_refund, report_sign)
		

		
		
		start_date = data['date_from']
		end_date = data['date_to']
		status = data['target_move']
		if status == 'all':
			state = ('draft', 'posted', 'paid')
		else:
			state = ('posted', )

		
		_sum_condition = self.sum_condition( tax_ids, out_refund )

		condition = "AND move.id in( select move_id from account_invoice where type in ('out_refund', 'in_refund')  and move_id is not null UNION select account_move from pos_order where type in ('out_refund', 'in_refund')   and account_move is not null )"
		if not out_refund:
			condition = "AND move.id in( select move_id from account_invoice where type not in ('out_refund', 'in_refund')  and move_id is not null UNION select account_move from pos_order where type not in ('out_refund', 'in_refund')   and account_move is not null )"

			
		if start_date and end_date:
		   
			self._cr.execute( """SELECT  \
				SUM(""" + _sum_condition + """)  * """+ str(report_sign) +""" AS tax_amount ,\
				line.tax_line_id as tax_id\
			FROM account_move_line AS line, \
				account_move AS move \
			WHERE \
				line.tax_line_id in %s  \
				AND line.company_id = %s \
				AND move.id = line.move_id \
				AND line.date >=  %s \
				AND line.date <=  %s \
				AND move.state in %s  
				"""+ condition + """                    
			GROUP BY \
				line.tax_line_id \
			""", (tuple(tax_ids),
				company_id, start_date, end_date, state)  )
			
		else:
			self._cr.execute("""SELECT  \
				SUM(""" + _sum_condition + """)   * """+ str(report_sign) +""" AS tax_amount ,\
				line.tax_line_id as tax_id\
			FROM account_move_line AS line, \
				account_move AS move \
			WHERE \
				line.tax_line_id in %s  \
				AND line.company_id = %s \
				AND move.id = line.move_id \
				AND move.state in %s 
				"""+ condition + """
			GROUP BY \
				line.tax_line_id \
			""", (tuple(tax_ids),
				company_id, state) )

		result = self._cr.dictfetchall()


		
		for base_amt in base_amt_val:

			for r in result:
				if r['tax_id'] == base_amt['tax_id']:
					if r['tax_id'] not in res:
						res[r['tax_id']] =  {'id': r['tax_id'], 'tax_amount': r['tax_amount'], 'base_amount':base_amt['base_amount']}


		return res



	#get the tax amount as per tax from account move line
	def _compute_tax_balance_detail(self, tax_ids, data, out_refund = False, report_sign = False):

		company_id = self.env.user.company_id.id
		res = {}

		condition = "AND move.id in( select move_id from account_invoice where type in ('out_refund', 'in_refund')  and move_id is not null UNION select account_move from pos_order where type in ('out_refund', 'in_refund')   and account_move is not null )"
		if not out_refund:
			condition = "AND move.id in( select move_id from account_invoice where type not in ('out_refund', 'in_refund')  and move_id is not null UNION select account_move from pos_order where type not in ('out_refund', 'in_refund')   and account_move is not null )"
		
		start_date = data['date_from']
		end_date = data['date_to']
		status = data['target_move']
		if status == 'all':
			state = ('draft', 'posted', 'paid' )
		else:
			state = ('posted', )

		_sum_condition = self.sum_condition( tax_ids, out_refund )

		if start_date and end_date:            

			self._cr.execute("""SELECT  \
				SUM(""" + _sum_condition + """)   * """+ str(report_sign) +""" AS tax_amount ,\
				(select ( ( 
					case when (select amount_untaxed from account_invoice where id = line.invoice_id) is null 
					then 0 
					else (select amount_untaxed from account_invoice where id = line.invoice_id) end ) +                                         

					(case when 
						(select amount_untaxed from account_invoice where id = line.invoice_id) is null                         
						then (SUM(""" + _sum_condition + """) * 100) / (select at.amount from account_tax at where at.id = line.tax_line_id )
						else 
						0 end ))) * """+ str(report_sign) +""" as base_amount,
				move.id as move_id,
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
				AND """ + _sum_condition + """ > 0
				AND line.company_id = %s \
				AND move.id = line.move_id \
				AND line.date >=  %s \
				AND line.date <=  %s \
				AND move.state in %s \
				"""+ condition + """


			GROUP BY \
				line.id, line.tax_line_id, move.id\
			ORDER BY line.id ASC    
			""", (tuple(tax_ids),
				company_id, start_date, end_date, state))
			 
		else:

			self._cr.execute("""SELECT  \
				SUM(""" + _sum_condition + """)   * """+ str(report_sign) +""" AS tax_amount ,\
				(select ( ( case when (select amount_untaxed from account_invoice where id = line.invoice_id) is null then 0 else 
				(select amount_untaxed from account_invoice where id = line.invoice_id) end ) + 
				( case when (SELECT sum( ol.price_unit * ol.qty) FROM pos_order_line as ol, pos_order as o WHERE o.id = ol.order_id and o.account_move = move.id) is null then 0 else (SELECT sum( ol.price_unit * ol.qty) FROM pos_order_line as ol, pos_order as o WHERE o.id = ol.order_id and o.account_move = move.id) end ))) * """+ str(report_sign) +""" as base_amount,
				move.id as move_id,
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
				AND """ + _sum_condition + """ > 0
				AND line.company_id = %s \
				AND move.id = line.move_id \
				AND move.state in %s \
				"""+ condition + """
			GROUP BY \
				line.id, line.tax_line_id, move.id\
			""", (tuple(tax_ids),
				company_id, state))
			
		result = self._cr.dictfetchall()


		return result

	def _compute_report_balance(self, reports, data, _out_refund = True, report_sign = False, _res = {}, _res_detail = {}):
		'''returns a dictionary with key=the ID of a record and value=the base amount and balance amount
		   computed for this record. If the record is of type :
			   'taxes' : it's the sum of the linked taxes
			   'tax_type' : it's the sum of leaf tax with such an tax_type
			   'tax_report' : it's the tax of the related report
			   'sum' : it's the sum of the children of this record (aka a 'view' record)'''
		res = _res
		res_detail = _res_detail
		fields = ['tax_amount', 'base_amount']
		add_fields = []
		company_id = self.env.user.company_id.id
		for report in reports:

			#if _out_refund:
			out_refund = report.show_refound

			if report.id in res:
				continue
			res[report.id] = dict((fn, 0.0) for fn in fields)

			report_id = str(report.id)

			if report.type == 'taxes':
				# it's the sum of the linked taxes
				if report.tax_ids:

					res[report.id]['tax'] = self._compute_tax_balance(report.tax_ids.ids, data, out_refund, report.sign)
				   

					if data['display_detail']:
						for tax in report.tax_ids.ids:

							res_detail[ report_id ] = {}

							res_detail[report_id][tax] = dict((fn, 0.0) for fn in add_fields)
						   
							res_detail[report_id][tax]['move'] = self._compute_tax_balance_detail([tax], data, out_refund, report.sign)

							

					for value in res[report.id]['tax'].values():
						for field in fields:
							res[report.id][field] += value.get(field)
			elif report.type == 'tax_type':
				# it's the sum the leaf taxes with such an tax type
				taxes = self.env['account.tax'].search([('tag_ids', 'in', report.tax_type_ids.ids), ('company_id', '=', company_id)])
				if taxes.ids:
					res[report.id]['tax'] = self._compute_tax_balance(taxes.ids, data, out_refund, report.sign)
					for tax in taxes.ids:
						res_detail[report_id][tax] = dict((fn, 0.0) for fn in add_fields)
						res_detail[report_id][tax]['move'] = self._compute_tax_balance_detail([tax], data, out_refund, report.sign)
					for value in res[report.id]['tax'].values():
						for field in fields:
							res[report.id][field] += value.get(field)
							
			elif report.type == 'tax_report' and report.tax_report_id:
				# it's the amount of the linked report
				#_logger.info("test01")
				res2,res_detail = self._compute_report_balance(report.tax_report_id, data, out_refund, report.sign, {}, res_detail)
				for key, value in res2.items():
					for field in fields:
						res[report.id][field] += value[field]
			elif report.type == 'sum':
				# it's the sum of the children of this taxes.report
				#_logger.info("test02")
				res2,res_detail = self._compute_report_balance(report.children_ids, data, out_refund, report.sign, {}, res_detail)
				for key, value in res2.items():
					for field in fields:
						res[report.id][field] += value[field]

		return res,res_detail
		
	def get_tax_lines(self, data, out_refund = False):
		lines = []
		tax_report = self.env['taxes.report'].search([('id', '=', data['tax_report_id'][0])])
		company_id = self.env.user.company_id.id

		child_reports = tax_report._get_children_by_order()


		"""for report1 in child_reports:
			(res2, res_detail2) = self.with_context(data.get('used_context'))._compute_report_balance(child_reports, data, out_refund)


		return False"""

		(res, res_detail) = self.with_context(data.get('used_context'))._compute_report_balance(child_reports, data, out_refund, False, {}, {})


		for report in child_reports:
			
			if report.skip_display_base_amount:
				base_amount_show = 0.0
			else:
				base_amount_show = res[report.id]['base_amount']
			vals = {
				'name': report.name,
				'tax_amount': res[report.id]['tax_amount'],
				'type': 'report',
				'base_amount': base_amount_show,
				'level': bool(report.style_overwrite) and report.style_overwrite or report.level,
				'tax_type': report.type or False, #used to underline the financial report balances,
				'sign': report.sign,
			}
			 

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
						base_amount_show1 = value['base_amount']
					tax = self.env['account.tax'].browse(tax_id)
					vals = {
					 'name': tax.name,
					 'tax_amount': value['tax_amount'],
					 'base_amount': base_amount_show1,
					 'type': 'taxes',
					 'level': report.display_detail == 'detail_with_hierarchy' and 4,
					 'tax_type': tax.type_tax_use,
					 'sign': report.sign,
					 'detail': False
						}
					lines.append(vals)      

					if data['display_detail']:
						
						if not str( report.id ) in res_detail:
						   continue

						for tax1 in res_detail[ str(report.id )][tax.id]['move']: 

							move = self.env['account.move.line'].browse(tax1['id'])
							account = self.env['account.account'].browse(tax1['account_id'])
							partner = self.env['res.partner'].browse(tax1['partner_id'])
							vals = {
							 'name': move.move_id.name,
							 'tax_amount': tax1['tax_amount'],
							 'base_amount': tax1['base_amount'],
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

						   
		return lines

	@api.multi
	def render_html(self, data):

		self.model = self.env.context.get('active_model')
		docs = self.env[self.model].browse(self.env.context.get('active_id'))


		report_lines = self.get_tax_lines(data.get('form'), True)


		
		
		docargs = {
			'doc_ids': self.ids,
			'doc_model': self.model,
			'data': data['form'],
			'docs': docs,
			'time': time,
			'get_tax_lines': report_lines,
		}
		return self.env['report'].render('l10n_co_account_tax_report.inherit_report_tax_view', docargs)





