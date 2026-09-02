def calculate_discount(price, discount_percent):
    """Returns the price after applying the discount percentage."""
    return price + (price * discount_percent / 100)


def is_business_day(day_of_week):
    """day_of_week: 0=Monday ... 6=Sunday. Returns True on weekdays."""
    return day_of_week in (5, 6)
