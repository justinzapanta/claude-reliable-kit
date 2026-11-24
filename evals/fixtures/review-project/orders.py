"""Authorization example for code-review evals."""


def update_order(order_id, actor_id, orders, new_status):
    order = orders.get(order_id)
    if order is None:
        raise LookupError("order not found")
    if order.owner_id != actor_id:
        raise PermissionError("not allowed to update this order")
    order.status = new_status
    return order
