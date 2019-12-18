# -*- coding: utf-8 -*-
# Copyright 2019 Coop IT Easy SCRLfs
#   - Vincent Van Rossem <vincent@coopiteasy.be>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import math
from pytz import timezone, UTC

from openerp import models, fields, api, _


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

    @api.onchange("date_from")
    def onchange_date_from(self):
        res = super(HrHolidays, self).onchange_date_from(
            self.date_to, self.date_from
        )

        # Workaround for api incompatibility:
        if type(res) is dict and res.has_key("value"):
            for field, value in res.get("value").items():
                if hasattr(self, field):
                    setattr(self, field, value)

        diff_day = self._compute_number_of_days(
            self.employee_id, self.date_from, self.date_to
        )
        self.number_of_days_temp = diff_day

    @api.onchange("date_to")
    def onchange_date_to(self):
        res = super(HrHolidays, self).onchange_date_to(
            self.date_to, self.date_from
        )

        # Workaround for api incompatibility:
        if type(res) is dict and res.has_key("value"):
            for field, value in res.get("value").items():
                if hasattr(self, field):
                    setattr(self, field, value)

        diff_day = self._compute_number_of_days(
            self.employee_id, self.date_from, self.date_to
        )
        self.number_of_days_temp = diff_day

    @api.onchange("period")
    def onchange_period(self):
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

    def _replace_duration(self, date_from, date_to, hour_from, hour_to):
        hour, minute = floatime_to_hour_minute(hour_from)
        utc_date_from = self._get_utc_date(date_from, hour, minute)

        hour, minute = floatime_to_hour_minute(hour_to)
        utc_date_to = self._get_utc_date(date_to, hour, minute)
        return utc_date_from, utc_date_to

    def _compute_number_of_days(self, employee_id, date_from, date_to):
        """ Returns a float equals to the timedelta between two dates given as string."""
        diff_day = self._get_number_of_days(date_from, date_to)

        if employee_id:
            employee = self.env["hr.employee"].browse(employee_id.id)
            company = self.env["res.company"].browse(employee_id.company_id.id)
            from_dt = fields.Datetime.from_string(date_from)
            to_dt = fields.Datetime.from_string(date_to)
            contracts = employee.sudo().contract_ids
            hours = 0.0
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
            return hours / company.hours_per_day
        return diff_day

    def _get_utc_date(self, day, hour, minute):
        context_tz = timezone(self._context.get("tz") or self.env.user.tz)
        day_time = day.replace(hour=hour, minute=minute)
        day_local_time = context_tz.localize(day_time)
        day_utc_time = day_local_time.astimezone(UTC)
        return day_utc_time
