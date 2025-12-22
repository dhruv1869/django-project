from datetime import timedelta

def calculate_leave_with_weekend_sandwich(start_date, end_date, half_day_start_type=None, half_day_end_type=None):
    """
    Calculate leave days including sandwich weekends.
    Returns: (total_days, sandwich_days)
    """

    total_days = 0
    sandwich_days = 0

    current_date = start_date

    while current_date <= end_date:
        weekday = current_date.weekday()  

        if weekday >= 5:
            sandwich_days += 1
        else:
            total_days += 1

        current_date += timedelta(days=1)

    return total_days, sandwich_days
