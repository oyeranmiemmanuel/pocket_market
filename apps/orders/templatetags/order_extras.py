from django import template

register = template.Library()


@register.filter
def group_items_by_seller(items):
    """
    Groups an iterable of OrderItem objects by their `seller`
    (apps.sellers.models.SellerProfile, snapshotted on the item at
    checkout time - see OrderItem.seller). seller is None for
    platform-owned products.

    Returns a list of dicts: [{"seller": <SellerProfile|None>, "items": [...]}, ...]

    Implemented as a template filter, not a queryset change in the view,
    because Django's {% regroup %} requires the input to already be
    sorted by the grouping key, and order.items.all() is only ordered
    by id (OrderItem.Meta.ordering). This works regardless of that
    ordering and safely handles items with no seller, which plain
    {% regroup %} does not (it raises on None comparisons during sort).
    """
    groups = {}
    order_seen = []

    for item in items:
        key = item.seller_id
        if key not in groups:
            groups[key] = {"seller": item.seller, "items": []}
            order_seen.append(key)
        groups[key]["items"].append(item)

    grouped = [groups[key] for key in order_seen]
    grouped.sort(
        key=lambda g: (
            g["seller"] is None,
            g["seller"].store_name.lower() if g["seller"] else "",
        )
    )
    return grouped
