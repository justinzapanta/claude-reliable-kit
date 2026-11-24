"""Small storefront pricing module used by the comparative evals."""


def tax_cents(subtotal_cents: int, rate_basis_points: int) -> int:
    """Return tax in cents for a nonnegative subtotal and rate."""
    if subtotal_cents < 0 or rate_basis_points < 0:
        raise ValueError("subtotal and rate must be nonnegative")
    return subtotal_cents * rate_basis_points // 10_000


def order_total_cents(subtotal_cents: int, rate_basis_points: int) -> int:
    return subtotal_cents + tax_cents(subtotal_cents, rate_basis_points)
