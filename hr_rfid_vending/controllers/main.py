# -*- coding: utf-8 -*-
from odoo import http, fields, exceptions
from odoo.http import request
from functools import reduce

from odoo.addons.hr_rfid.controllers.main import WebRfidController

import operator
import datetime


class HrRfidVending(WebRfidController):
    @http.route(['/hr/rfid/event'], type='json', auth='none', method=['POST'], csrf=False)
    def post_event(self, **post):
        print('post=' + str(post))

        webstacks_env = request.env['hr.rfid.webstack'].sudo()
        cmd_env = request.env['hr.rfid.command'].sudo()
        ev_env = request.env['hr.rfid.vending.event'].sudo()
        webstack = webstacks_env.search([ ('serial', '=', str(post['convertor'])) ])
        status_code = 200

        def ret_super():
            return super(HrRfidVending, self).post_event(**post)

        def ret_check_for_unsent_cmd(status_code, event=None):
            return super(HrRfidVending, self).check_for_unsent_cmd(status_code, event)

        def create_ev(controller, event, card, ev_num, item_sold_id=None, transaction_price=None):
            ev = {
                'action_selection': ev_num,
                'event_time': event['date'] + event['time'],
                'controller_id': controller.id,
            }
            if len(card) > 0:
                ev['card_id'] = card.id
                ev['employee_id'] = card.employee_id
            if item_sold_id is not None and len(item_sold_id) > 0:
                ev['item_sold_id'] = item_sold_id.id
            if transaction_price is not None:
                ev['transaction_price'] = transaction_price
            return ev_env.create(ev)

        def get_employee_balance(employee, controller):
            balance = employee.hr_rfid_vending_balance
            if employee.hr_rfid_vending_in_attendance is True:
                balance += employee.hr_rfid_vending_limit
            balance = int(int(balance * 100) / controller.scale_factor)
            if balance > 0xFF:
                balance = 0xFF
            b1 = int((balance & 0xF0) / 0x10)
            b2 = balance & 0x0F
            return '%02X%02X' % (b1, b2), balance

        def parse_event():
            controller = webstack.controllers.filtered(lambda r: r.ctrl_id == post['event']['id'])
            event = post['event']
            if len(controller) == 0:
                return ret_super()

            # If it's not a vending controller
            if controller.hw_version != '16':
                return ret_super()

            card_env = request.env['hr.rfid.card'].sudo()

            # TODO Move into function "deal_with_ev_64"
            if event['event_n'] == 64:
                card = card_env.search([ ('number', '=', event['card']) ])

                if len(card) == 0 or len(card.employee_id) == 0:
                    return ret_super()

                emp = card.employee_id

                if emp.hr_rfid_vending_in_attendance is True \
                        and emp.attendance_state != 'checked_in':
                    return ret_super()

                date = datetime.datetime.strptime(
                    event['date'] + ' ' + event['time'],
                    '%m.%d.%y %H:%M:%S'
                )
                if date + datetime.timedelta(minutes=5) <= datetime.datetime.now():
                    ev = create_ev(controller, event, card, '64')
                    return ret_check_for_unsent_cmd(status_code, ev)

                if event['bos'] < event['tos']:
                    ev = create_ev(controller, event, card, '64')
                    return ret_check_for_unsent_cmd(status_code, ev)

                balance_str, balance = get_employee_balance(card.employee_id, controller)
                card_number = reduce(operator.add, list('0' + str(a) for a in card.number), '')

                ev = create_ev(controller, event, card, '64')
                cmd_env.create({
                    'webstack_id': webstack.id,
                    'controller_id': controller.id,
                    'cmd': 'DB',
                    'cmd_data': '4000' + card_number + balance_str,
                    'sent_balance': balance,
                })
                return ret_check_for_unsent_cmd(status_code, ev)
            # TODO Move into function "deal_with_ev_47"
            elif event['event_n'] == 47:
                card = card_env.search([ ('number', '=', event['card']) ])

                if len(card) == 0:
                    if event['card'] != '0000000000':
                        return ret_super()
                elif len(card.employee_id) == 0:
                    return ret_super()

                item_number = int(event['dt'][4:6], 16)
                row = int(item_number / 4)
                item_number -= 1
                item_number %= 4
                item_number += 1

                if row < 1 or row > 18:
                    ev = create_ev(controller, event, card, '-1')
                    return ret_check_for_unsent_cmd(status_code, ev)

                rows_env = self.env['hr.rfid.ctrl.io.table.row']
                row = rows_env.search({
                    'controller_id': controller.id,
                    'row_num': row,
                })

                if len(row) == 0:
                    controller.create_vending_rows()
                    row = rows_env.search({
                        'controller_id': controller.id,
                        'row_num': row,
                    })

                if item_number == 1:
                    item = row.item1
                elif item_number == 2:
                    item = row.item2
                elif item_number == 3:
                    item = row.item3
                else:
                    item = row.item4
                # TODO Reduce item quantity

                if len(card) > 0:
                    last_ev = ev_env.search([
                        ('controller_id', '=', controller.id),
                        ('event_action', '=', '64'),
                        ('card_id', '=', card.id),
                    ])
                    if len(last_ev) == 0:
                        raise exceptions.ValidationError(
                            'Controller knows the balance of a user but we never sent it the balance????'
                        )
                    last_balance = last_ev[-1].sent_balance
                    if last_balance < -1:
                        raise exceptions.ValidationError('???????????????')
                    received_balance = int(event['dt'][10:12], 16)*0x16 + int(event['dt'][12:14], 16)
                    difference = last_balance - received_balance
                    difference *= controller.scale_factor
                    difference /= 100
                    card.employee_id.hr_rfid_vending_purchase(difference)
                    ev = create_ev(controller, event, card, '47', item, difference)
                else:
                    cash = int(event['dt'][10:12], 16)*0x16 + int(event['dt'][12:14], 16)
                    cash *= controller.scale_factor
                    cash /= 100
                    controller.cash_contained = controller.cash_contained + cash
                    ev = create_ev(controller, event, card, '47', item, cash)

                return ret_check_for_unsent_cmd(status_code, ev)
            # TODO Move into function "deal_with_err_evs"
            elif event['event_n'] in [48, 49]:
                card = card_env.search([ ('number', '=', event['card']) ])
                ev = create_ev(controller, event, card, str(event['event_n']))
                return ret_check_for_unsent_cmd(status_code, ev)

            return ret_super()

        if 'event' in post:
            ret = parse_event()
        else:
            ret = ret_super()

        print('ret=' + str(ret))
        return ret

