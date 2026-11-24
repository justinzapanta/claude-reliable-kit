# Checkout product context

- Storefront uses a Python service and a third-party payment provider.
- We currently support one-time card payments and full order cancellation before fulfillment.
- The team wants saved payment methods and refunds, but no provider API, retention period, partial-refund policy, or restocking policy has been selected.
- Payment data must stay with the provider; do not store raw card numbers or security codes.
- The next release window starts in four weeks. No implementation has been approved yet.

This brief deliberately leaves product decisions open. A good planning or discovery run should surface the decisions, not silently fill them in.
