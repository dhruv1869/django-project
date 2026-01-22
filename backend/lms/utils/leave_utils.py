
from datetime import timedelta, date
import schedule
import time
from django.db import transaction
from lms.models import Holiday, LeaveBalance
from lms.log_app import loggers  



def is_weekend(day):
    return day.weekday() >= 5


def is_holiday(day):
    return Holiday.objects.filter(festival_date=day).exists()


def is_non_working_day(day):
    return is_weekend(day) or is_holiday(day)


def calculate_leave_with_weekend_sandwich(
    start_date,
    end_date,
    half_day_start_type=None,
    half_day_end_type=None
):
    try:
        applied_leave_days = 0
        sandwich_days = 0

        current_date = start_date
        while current_date <= end_date:
            applied_leave_days += 1
            current_date += timedelta(days=1)

        prev_day = start_date - timedelta(days=1)
        while is_non_working_day(prev_day):
            sandwich_days += 1
            prev_day -= timedelta(days=1)

        next_day = end_date + timedelta(days=1)
        while is_non_working_day(next_day):
            sandwich_days += 1
            next_day += timedelta(days=1)

        total_days = applied_leave_days + sandwich_days

        if half_day_start_type:
            total_days -= 0.5
        if half_day_end_type:
            total_days -= 0.5

        loggers.info(
            f"Leave calculated | Start: {start_date} | End: {end_date} | "
            f"Total: {total_days} | Sandwich: {sandwich_days}"
        )

        return total_days, sandwich_days

    except Exception:
        loggers.error(
            "Error calculating leave with weekend sandwich",
            exc_info=True
        )
        return 0, 0



def add_casual_leave_every_minute():
    loggers.info("Casual leave scheduler job started")

    try:
        with transaction.atomic():
            balances = LeaveBalance.objects.select_for_update()

            for balance in balances:
                old_leave = balance.casual_leave

                balance.casual_leave += 0.5
                balance.total_casual_leave += 0.5
                balance.save(update_fields=["casual_leave", "total_casual_leave"])

                loggers.info(
                    f"Employee {balance.employee_id} | "
                    f"Casual: {old_leave} → {balance.casual_leave}"
                )

        loggers.info("Casual leave scheduler job completed successfully")

    except Exception:
        loggers.error(
            "Error in casual leave scheduler job",
            exc_info=True
        )



def start_scheduler():
    loggers.info("Initializing leave scheduler")

    schedule.every(1).minutes.do(add_casual_leave_every_minute)

    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception:
            loggers.error(
                "Error running scheduler loop",
                exc_info=True
            )




