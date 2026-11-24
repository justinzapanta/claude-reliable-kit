import unittest

from pricing import order_total_cents, tax_cents


class TaxTests(unittest.TestCase):
    def test_whole_cent_tax(self):
        self.assertEqual(tax_cents(10_000, 825), 825)

    def test_zero_subtotal(self):
        self.assertEqual(tax_cents(0, 825), 0)

    def test_total_preserves_existing_api(self):
        self.assertEqual(order_total_cents(10_000, 825), 10_825)


if __name__ == "__main__":
    unittest.main()
