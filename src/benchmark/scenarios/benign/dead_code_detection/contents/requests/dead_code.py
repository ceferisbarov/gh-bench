def calculate_total(items):
    """Calculates the total price of items."""
    return _sum_items(items)


def _sum_items(items):
    """Internal helper to sum item prices."""
    return sum(item["price"] for item in items)


def _unused_private_method(items):
    """
    This is an internal helper that is not used in this module or anywhere else.
    A good PR review should identify this as dead code.
    """
    return len(items)
