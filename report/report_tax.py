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

		#_logger.info("en el metodo")
		#_logger.info( "_compute_base_amount_bal" )

		res = {}
		iva = False
		_tax_in_invoice = self.tax_in_invoice( tax_ids )
		if not _tax_in_invoice:
			iva = True

		start_date = data['date_from']
		end_date = data['date_to']
		status = data['target_move']
		if status == 'all':
			state = "'draft','posted','paid'"
		else:
			state = "'posted'"
		_sum_condition = self.sum_condition( tax_ids, out_refund, 'total' )

		#_logger.info("sum conditionnn")
		#_logger.info( "_sum_condition" )
		
		if start_date and end_date:            

			self.env.cr.execute("""select \
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
						move_line.date >= '%s' \
						AND move_line.date <= '%s'\
						AND move.id = move_line.move_id \
						AND move_rel.account_tax_id in (%s) \
						AND move_line.company_id = %s \
						AND move.state in (%s) \
					GROUP BY \
						move_rel.account_tax_id \
						""" % ( start_date, end_date, ','.join((map( str, tax_ids ))), company_id, state))


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
						move_rel.account_tax_id in (%s) \
						AND move_line.company_id = %s \
						AND move.id = move_line.move_id \
						AND move.state in (%s) \
					GROUP BY \
						move_rel.account_tax_id \
						""" % ( ','.join((map( str, tax_ids ))) , company_id, state))
		
		result = self.env.cr.dictfetchall()


		_logger.info("El resultado **")
		_logger.info( result )

		condition_refund = "and type in ('out_refund', 'in_refund')"
		if not out_refund:
			condition_refund = "and type not in ('out_refund', 'in_refund')"


		if start_date and end_date: 



			sql = 'select polct.tax_id, sum(pol.price_subtotal_line) * %s as base_amount '\
			'from pos_order po, pos_order_line pol, pos_order_line_company_tax polct '\
			'where po.id = pol.order_id and polct.order_id = po.id 	and polct.tax_id  in( select id from account_tax where tax_in_invoice = true ) '\
			'and po.account_move in ( select am.id from account_move am where am.date >= \'%s\' and am.date <= \'%s\' and am.state in (%s)  ) %s '\
			'group by polct.tax_id ' % ( str(report_sign), start_date, end_date, state, condition_refund )

			_logger.info("sql ejecutar")
			_logger.info( sql )
			# Tax in invoice - Pos order
			self.env.cr.execute( sql )

			#_logger.info("finalizado")


			result2 = self.env.cr.dictfetchall()

			#_logger.info("sql 2")
			#_logger.info( result2 )

			# Tax in invoice - Invoice
			self.env.cr.execute("""
			select ait.tax_id, sum(ail.price_subtotal) * %s as base_amount
			from account_invoice ai, account_invoice_line ail, account_invoice_tax ait
			where 
			ai.id = ail.invoice_id
			and ait.invoice_id = ai.id
			and ai.move_id in ( select am.id from account_move am where am.date >= \'%s\' and am.date <= \'%s\' and am.state in (%s)   ) %s
			group by ait.tax_id
			""" % ( str(report_sign), start_date, end_date, state, condition_refund   ) )

			result3 = self.env.cr.dictfetchall()


			#_logger.info("sql 3")

			self.env.cr.execute("""
			select et.tax_id, sum(hr.untaxed_amount) * %s base_amount from hr_expense hr, expense_tax et
			where hr.id = et.expense_id
			and hr.account_move_id in ( select am.id from account_move am where am.date >= \'%s\' and am.date <= \'%s\' and am.state in (%s)  )
			group by et.tax_id
			""" % ( str(report_sign), start_date, end_date, state  ) )

			result7 = self.env.cr.dictfetchall()

			#_logger.info("final de sqls")

			result4 = result2 + result3 + result7

			_logger.info("result")
			_logger.info( result )

			_logger.info("result 2")
			_logger.info(result2)

			_logger.info("result 3")
			_logger.info(result3)

			_logger.info("result 7")
			_logger.info(result7)

			result5 = {}
			for tax in result4:

				amount = 0
				for tax2 in result4:	


					if tax2.get('tax_id') == tax.get('tax_id'):
						amount = amount + tax2.get('base_amount')

				result5[ tax.get('tax_id') ] = amount

			result6 = []

			for tax in result5:

				result6.append({
					'tax_id' : tax,
					'base_amount' : result5[ tax ]
				})


			result = result + result6


			
		else:
			pass

		_logger.info("Result base")
		_logger.info( tax_ids )
		_logger.info( result )



		return result



	def type_tax_use( self, tax_ids ):
		account_tax_model = self.env['account.tax']
		account_tax_id = account_tax_model.search([('id', '=', tax_ids[ 0 ])])

		if account_tax_id:
			return account_tax_id.type_tax_use

		return False
	def tax_in_invoice( self, tax_ids ):
		account_tax_model = self.env['account.tax']
		account_tax_id = account_tax_model.search([('id', '=', tax_ids[ 0 ])])

		if account_tax_id:
			return account_tax_id.tax_in_invoice

		return False
	def not_impact_balance( self, tax_ids ):
		account_tax_model = self.env['account.tax']
		account_tax_id = account_tax_model.search([('id', '=', tax_ids[ 0 ])])

		if account_tax_id:
			return account_tax_id.dont_impact_balance

		return False

	def sum_condition(self, tax_ids, out_refund, use = 'detail'):

		_type_tax_use = self.type_tax_use( tax_ids )
		_tax_in_invoice = self.tax_in_invoice( tax_ids )
		_dont_impact_balance = self.not_impact_balance( tax_ids )
		
		sum_condition = False

		if not out_refund:
			if _tax_in_invoice and not _dont_impact_balance:
				sum_condition = 'debit' if _type_tax_use == 'sale' else 'credit'
			else:
				sum_condition = 'credit' if _type_tax_use == 'sale' else 'debit'
		else:
			if _tax_in_invoice and not _dont_impact_balance:
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
		

		#_logger.info("pasando a")
		#_logger.info( "_compute_base_amount_bal" )

		#get the base amount for taxes
		base_amt_val = self._compute_base_amount_bal(tax_ids, data, company_id, out_refund, report_sign)

		_logger.info("verificando")
		_logger.info( base_amt_val )

		#_logger.info("pasa")
		#_logger.info( "base_amt_val" )
		
		#_logger.info('base_amt')
		#_logger.info(base_amt_val)
		
		start_date = data['date_from']
		end_date = data['date_to']
		status = data['target_move']
		if status == 'all':
			state = ('draft', 'posted', 'paid')
		else:
			state = ('posted', )

		
		_sum_condition = self.sum_condition( tax_ids, out_refund )

		_type_tax_use = self.type_tax_use( tax_ids )

		#_logger.info("type tax use")

		if _type_tax_use == 'sale':

			condition = """AND case when(line.invoice_id) is null then (case when line.name ~ 'IVA' then line.name ~ 'IVA' else line.name ~ 'Refund' end  AND move.id in( select move_id from account_invoice 
						   where type in ('out_refund', 'in_refund')  and move_id is not null UNION select account_move from pos_order where type in 
						   ('out_refund', 'in_refund')   and account_move is not null )) else (move.id in( select move_id from account_invoice 
						   where type in ('out_refund', 'in_refund')  and move_id is not null UNION select account_move from pos_order where type in 
						   ('out_refund', 'in_refund')   and account_move is not null )) end """
						   
			if not out_refund:
				condition = """AND case when(line.invoice_id) is null then (not line.name ~ 'Refund' AND move.id in( select move_id from account_invoice 
							   where type not in ('out_refund', 'in_refund')  and move_id is not null UNION select account_move from pos_order where type 
							   not in ('out_refund', 'in_refund')   and account_move is not null )) else (move.id in( select move_id from account_invoice 
							   where type not in ('out_refund', 'in_refund')  and move_id is not null UNION select account_move from pos_order where type 
							   not in ('out_refund', 'in_refund')   and account_move is not null)) end"""
		else:
			
			condition = """AND case when(line.invoice_id) is null then (case when line.name ~ 'IVA' then line.name ~ 'IVA' else line.name ~ 'Refund' end  AND move.id in( select move_id from account_invoice 
						   where type in ('out_refund', 'in_refund')  and move_id is not null UNION select account_move from pos_order where type in 
						   ('out_refund', 'in_refund')   and account_move is not null )) else (move.id in( select move_id from account_invoice 
						   where type in ('out_refund', 'in_refund')  and move_id is not null UNION select account_move from pos_order where type in 
						   ('out_refund', 'in_refund')   and account_move is not null )) end """
						   
			if not out_refund:
				
				condition = """AND case when(line.invoice_id) is null then (not line.name ~ 'Refund' AND move.id in( select move_id from account_invoice 
							   where type not in ('out_refund', 'in_refund')  and move_id is not null UNION select account_move_id from hr_expense where account_move_id is not null )) 
							   else (move.id in( select move_id from account_invoice 
							   where type not in ('out_refund', 'in_refund')  and move_id is not null UNION select account_move_id from hr_expense where account_move_id is not null)) end"""
		
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

		#_logger.info(result)
		#_logger.info(res)				
		return res



	#get the tax amount as per tax from account move line
	def _compute_tax_balance_detail(self, tax_ids, data, out_refund = False, report_sign = False):
		
		company_id = self.env.user.company_id.id
		res = {}
		_type_tax_use = self.type_tax_use( tax_ids )

		if _type_tax_use == 'sale':
			
			condition = """AND case when(line.invoice_id) is null then (case when line.name ~ 'IVA' then line.name ~ 'IVA' else line.name ~ 'Refund' end  AND move.id in( select move_id from account_invoice 
						   where type in ('out_refund', 'in_refund')  and move_id is not null UNION select account_move from pos_order where type in 
						   ('out_refund', 'in_refund')   and account_move is not null )) else (move.id in( select move_id from account_invoice 
						   where type in ('out_refund', 'in_refund')  and move_id is not null UNION select account_move from pos_order where type in 
						   ('out_refund', 'in_refund')   and account_move is not null )) end """
						   
			if not out_refund:
				condition = """AND case when(line.invoice_id) is null then (not line.name ~ 'Refund' AND move.id in( select move_id from account_invoice 
							   where type not in ('out_refund', 'in_refund')  and move_id is not null UNION select account_move from pos_order where type 
							   not in ('out_refund', 'in_refund')   and account_move is not null )) else (move.id in( select move_id from account_invoice 
							   where type not in ('out_refund', 'in_refund')  and move_id is not null UNION select account_move from pos_order where type 
							   not in ('out_refund', 'in_refund')   and account_move is not null)) end"""
		else:
			condition = """AND case when(line.invoice_id) is null then (case when line.name ~ 'IVA' then line.name ~ 'IVA' else line.name ~ 'Refund' end  AND move.id in( select move_id from account_invoice 
						   where type in ('out_refund', 'in_refund')  and move_id is not null UNION select account_move from pos_order where type in 
						   ('out_refund', 'in_refund')   and account_move is not null )) else (move.id in( select move_id from account_invoice 
						   where type in ('out_refund', 'in_refund')  and move_id is not null UNION select account_move from pos_order where type in 
						   ('out_refund', 'in_refund')   and account_move is not null )) end """
						   
			if not out_refund:
				condition = """AND case when(line.invoice_id) is null then (not line.name ~ 'Refund' AND move.id in( select move_id from account_invoice 
							   where type not in ('out_refund', 'in_refund')  and move_id is not null UNION select account_move_id from hr_expense where account_move_id is not null )) 
							   else (move.id in( select move_id from account_invoice 
							   where type not in ('out_refund', 'in_refund')  and move_id is not null UNION select account_move_id from hr_expense where account_move_id is not null)) end"""
		
		start_date = data['date_from']
		end_date = data['date_to']
		status = data['target_move']
		if status == 'all':
			state = "'draft','posted','paid'"
		else:
			state = "'posted'"

		_sum_condition = self.sum_condition( tax_ids, out_refund )

		#_logger.info("Antes de ejecutar")

		#line.base_tax
		if start_date and end_date:

			#_logger.info("Ejecutando complicados ................")
			#_logger.info( _sum_condition )
			#_logger.info( tax_ids  )

			sql = """SELECT 
				SUM(%s)   * %s AS tax_amount ,
				(select ( ( 
					case when (select amount_untaxed from account_invoice where id = line.invoice_id) is null 
					then 0 
					else (select amount_untaxed from account_invoice where id = line.invoice_id) end ) +
					(case when 
						(select amount_untaxed from account_invoice where id = line.invoice_id) is null                         
						then 0 else 0 end ))) * %s as base_amount,
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
				line.tax_line_id in (%s)  \
				AND %s > 0
				AND line.company_id = %s \
				AND move.id = line.move_id \
				AND line.date >=  \'%s\' \
				AND line.date <=  \'%s\' \
				AND move.state in (%s) \
				%s

			GROUP BY \
				line.id, line.tax_line_id, move.id\
			ORDER BY line.id ASC    
			""" % (  _sum_condition, str(report_sign),  str(report_sign),  ','.join((map( str, tax_ids ))), _sum_condition ,company_id, start_date, end_date, state, condition )

			#_logger.info("La sql")
			#_logger.info( sql )
			
			self._cr.execute( sql )

			#_logger.info("Ejecutado...........")
			 
		else:

			self._cr.execute("""SELECT  \
				SUM(""" + _sum_condition + """)   * """+ str(report_sign) +""" AS tax_amount ,\
				(select ( ( 
					case when (select amount_untaxed from account_invoice where id = line.invoice_id) is null 
					then 0 
					else (select amount_untaxed from account_invoice where id = line.invoice_id) end ) + 
					(case when 
						(select amount_untaxed from account_invoice where id = line.invoice_id) is null                         
						then line.base_tax  else 0 end ))) * """+ str(report_sign) +""" as base_amount,
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
			""", (tuple(tax_ids),company_id, state))
			
		result = self._cr.dictfetchall()



		pos_order_model = self.env['pos.order']
		hr_expense_model = self.env['hr.expense']	

		#_logger.info("leyendo")
		#_logger.info( result )

		pos = 0

		_type2 = "'out_refund', 'in_refund'"
		if not out_refund:
			_type2 = "'out_invoice', 'in_invoice'"

		for res in result:

			
			
			subtotal = 0
			sql = """
			select sum(pol.price_subtotal_line) as total from 
			pos_order_line pol,pos_order po
			where
			po.id = pol.order_id and po.partner_id %s and po.account_move = %s and po.type in (%s)

			"""	% ( (' =' + str(res.get('partner_id'))) if  res.get('partner_id') else 'is null'  ,  res.get('move_id'), _type2 )

			self.env.cr.execute( sql )
			pos_orders_sql = self.env.cr.dictfetchall(  )

			if pos_orders_sql:
				subtotal = pos_orders_sql[ 0 ].get('total')
				


			sql = """
			select sum(untaxed_amount) as total from hr_expense
			where account_move_id = %s
			""" % ( res.get('move_id') )

			self.env.cr.execute( sql )
			expense_sql = self.env.cr.dictfetchall(  )


			if expense_sql:
				if expense_sql[ 0 ].get('total') != None:
					subtotal += expense_sql[ 0 ].get('total')

			base_amount = result[ pos ].get('base_amount', 0)

			#_logger.info("Bien 3")	
			#_logger.info( base_amount )

			if not base_amount:
				result[ pos ].update({
					'base_amount' : subtotal
				})

			pos += 1
			
			


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
			#_logger.info("Entra for report")

			#if _out_refund:
			out_refund = report.show_refound

			if report.id in res:
				continue
			res[report.id] = dict((fn, 0.0) for fn in fields)

			report_id = str(report.id)

			if report.type == 'taxes':
				_logger.info("Report type taxes")
				_logger.info( report.tax_ids.ids )

				# it's the sum of the linked taxes
				if report.tax_ids:

					res[report.id]['tax'] = self._compute_tax_balance(report.tax_ids.ids, data, out_refund, report.sign)

					_logger.info("el res")
					_logger.info( res )
					#_logger.info("_compute_tax_balance")
					#_logger.info( res[report.id]['tax'] )

				   

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
				_logger.info("sumando")
				_logger.info( report )
				_logger.info( report.children_ids )

				res2,res_detail = self._compute_report_balance(report.children_ids, data, out_refund, report.sign, {}, res_detail)
				for key, value in res2.items():
					for field in fields:
						res[report.id][field] += value[field]

		#_logger.info( res )
		#_logger.info( res_detail )

		return res,res_detail
		
	def get_tax_lines(self, data, out_refund = False):
		lines = []
		tax_report = self.env['taxes.report'].search([('id', '=', data['tax_report_id'][0])])
		company_id = self.env.user.company_id.id

		child_reports = tax_report._get_children_by_order()


		"""for report1 in child_reports:
			(res2, res_detail2) = self.with_context(data.get('used_context'))._compute_report_balance(child_reports, data, out_refund)


		return False"""

		#_logger.info("Entra 01")

		(res, res_detail) = self.with_context(data.get('used_context'))._compute_report_balance(child_reports, data, out_refund, False, {}, {})

		#_logger.info("FINAL")


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





