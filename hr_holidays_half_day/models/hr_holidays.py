# -*- coding: utf-8 -*-
# Copyright 2019 Coop IT Easy SCRLfs
#   - Vincent Van Rossem <vincent@coopiteasy.be>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import math
from pytz import timezone, UTC

from openerp import models, fields, api, _
from openerp.exceptions import ValidationError


def floatime_to_hour_minute(f):
    decimal, integer = math.modf(f)
    return int(integer), int(round(decimal * 60))


class HrHolidays(models.Model):
    _inherit = "hr.holidays"

    period = fields.Selection(
        string="Period",
        selection=[("am", "AM"), ("pm", "PM"), ("day", "Day")],
        default="day",
    )

    @api.onchange("holiday_status_id")
    def _onchange_holiday_status_id(self):
        self.number_of_days_temp = self._recompute_days()

    def _recompute_days(self):
        date_from = self.date_from
        date_to = self.date_to
        if (date_to and date_from) and (date_from <= date_to):
            duration = self._compute_number_of_days(
                self.employee_id.id, date_from, date_to
            )
            return duration

    @api.multi
    def onchange_employee(self, employee_id):
        res = super(HrHolidays, self).onchange_employee(employee_id)
        duration = self._recompute_days()
        res["value"]["number_of_days_temp"] = duration
        return res

    @api.multi
    def onchange_date_from(self, date_to, date_from):
        res = super(HrHolidays, self).onchange_date_from(date_to, date_from)
        employee_id = self.employee_id.id or self.env.context.get(
            "employee_id", False
        )
        if (date_to and date_from) and (date_from <= date_to):
            diff_day = self._compute_number_of_days(
                employee_id, date_from, date_to
            )
            res["value"]["number_of_days_temp"] = diff_day
        return res

    @api.multi
    def onchange_date_to(self, date_to, date_from):
        res = super(HrHolidays, self).onchange_date_to(date_to, date_from)
        employee_id = self.employee_id.id or self.env.context.get(
            "employee_id", False
        )
        if (date_to and date_from) and (date_from <= date_to):
            diff_day = self._compute_number_of_days(
                employee_id, date_from, date_to
            )
            res["value"]["number_of_days_temp"] = diff_day
        return res

    @api.onchange("period")
    def onchange_period(self):
        if self.type != "add":
            period = self.period
            from_dt = fields.Datetime.from_string(self.date_from)
            to_dt = fields.Datetime.from_string(self.date_to)

            company = self.env["res.company"].browse(
                self.employee_id.company_id.id
            )

            if period == "am":
                from_dt, to_dt = self._replace_duration(
                    from_dt, to_dt, company.am_hour_from, company.am_hour_to
                )
            elif period == "pm":
                from_dt, to_dt = self._replace_duration(
                    from_dt, to_dt, company.pm_hour_from, company.pm_hour_to
                )
            else:
                from_dt, to_dt = self._replace_duration(
                    from_dt, to_dt, company.am_hour_from, company.pm_hour_to
                )

            self.date_from = fields.Datetime.to_string(from_dt)
            self.date_to = fields.Datetime.to_string(to_dt)
            self.number_of_days_temp = self._recompute_days()

    def _replace_duration(self, date_from, date_to, hour_from, hour_to):
        hour, minute = floatime_to_hour_minute(hour_from)
        utc_date_from = self._get_utc_date(date_from, hour, minute)

        hour, minute = floatime_to_hour_minute(hour_to)
        utc_date_to = self._get_utc_date(date_to, hour, minute)
        return utc_date_from, utc_date_to

    def _compute_number_of_days(self, employee_id, date_from, date_to):
        """ Returns a float equals to the timedelta between two dates given as string."""
        hours = 0.0
        if employee_id:
            employee = self.env["hr.employee"].browse(employee_id)
            company = self.env["res.company"].browse(employee.company_id.id)
            if not company.hours_per_day:
                raise ValidationError(
                    _("You must define company working hours")
                )
            from_dt = fields.Datetime.from_string(date_from)
            to_dt = fields.Datetime.from_string(date_to)
            contracts = employee.sudo().contract_ids
            for contract in contracts:
                for calendar in contract.working_hours:
                    working_hours = calendar.get_working_hours(
                        from_dt,
                        to_dt,
                        resource_id=calendar.id,
                        compute_leaves=True,
                    )
                    hours += sum(wh for wh in working_hours)
            if hours:
                hours /= company.hours_per_day
        return hours

    def _get_utc_date(self, day, hour, minute):
        tz = self._context.get("tz") or self.env.user.tz
        if not tz:
            raise ValidationError(
                _("You must define a timezone for this user")
            )
        context_tz = timezone(self._context.get("tz") or self.env.user.tz)
        day_time = day.replace(hour=hour, minute=minute)
        day_local_time = context_tz.localize(day_time)
        day_utc_time = day_local_time.astimezone(UTC)
        return day_utc_time
