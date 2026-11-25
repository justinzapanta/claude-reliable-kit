#!/usr/bin/env python3
"""Generate the "shop-app" benchmark fixture: ~100 files of Python backend + React/TS frontend with seeded tasks.

Usage: python make_shop_app.py OUT_DIR --task {browser,review,impact,tests} [--memory]

Every run produces byte-identical files, so runs are comparable. Each task leaves the repo in the state the
prompt expects (a clean commit, or an uncommitted change for "review"). --memory seeds project memory in
.git/lean-memory.json the same way task-ledger's memory.py stores it. Ground truth for grading is printed as
JSON on the last line.
"""
import argparse
import datetime
import json
import subprocess
from pathlib import Path

SERVICES = {
    "money": ["to_cents", "from_cents", "round_half_up", "format_price"],
    "tax": ["tax_cents", "tax_rate_for", "tax_breakdown"],
    "pricing": ["line_total", "subtotal", "order_total"],
    "discounts": ["sale_price", "apply_coupon", "best_discount"],
    "shipping": ["shipping_cost", "free_shipping_threshold", "estimate_days"],
    "inventory": ["reserve", "release", "in_stock"],
    "refunds": ["refundable_amount", "issue_refund", "refund_window_open"],
    "auth": ["current_user", "require_login", "is_admin"],
    "audit": ["record", "recent_events"],
    "notifications": ["send_receipt", "send_refund_notice", "send_low_stock_alert"],
}
APIS = {
    "orders": [("GET", "/api/orders/<order_id>"), ("POST", "/api/orders"), ("GET", "/api/orders/<order_id>/items")],
    "cart": [("GET", "/api/cart"), ("POST", "/api/cart/items"), ("DELETE", "/api/cart/items/<item_id>")],
    "checkout": [("POST", "/api/checkout"), ("GET", "/api/checkout/quote")],
    "products": [("GET", "/api/products"), ("GET", "/api/products/<product_id>")],
    "refunds": [("POST", "/api/refunds"), ("GET", "/api/refunds/<refund_id>")],
    "users": [("GET", "/api/users/me"), ("PATCH", "/api/users/me")],
    "admin": [("GET", "/api/admin/audit"), ("POST", "/api/admin/stock")],
    "search": [("GET", "/api/search")],
    "health": [("GET", "/api/health")],
}
COMPONENTS = ["Header", "Footer", "ProductCard", "ProductList", "ProductPage", "CartButton", "CartDrawer", "CartLine",
              "CartSummary", "CheckoutForm", "AddressForm", "PaymentForm", "OrderList", "OrderDetail", "RefundForm",
              "SearchBar", "Spinner", "ErrorBanner", "AccountPage", "AdminPanel"]
HOOKS = ["useCart", "useCartTotals", "useProducts", "useOrders", "useUser", "useSearch", "useRefunds", "useCheckout"]


def w(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes((text.lstrip("\n")).encode("utf-8"))


def backend(root, tax_bug, ship_bug=False):
    w(root, "backend/__init__.py", "")
    w(root, "backend/services/__init__.py", "")
    w(root, "backend/api/__init__.py", "")
    w(root, "backend/models/__init__.py", "")
    w(root, "backend/services/money.py", '''
"""Money helpers. All amounts are integer cents."""


def to_cents(amount):
    return int(round(float(amount) * 100))


def from_cents(cents):
    return cents / 100


def round_half_up(numerator, denominator):
    return (numerator * 2 + denominator) // (denominator * 2)


def format_price(cents):
    return f"${from_cents(cents):,.2f}"
''')
    tax_line = "    return subtotal_cents * rate_bp // 10_000" if tax_bug else \
        "    return round_half_up(subtotal_cents * rate_bp, 10_000)"
    w(root, "backend/services/tax.py", f'''
from backend.services.money import round_half_up, to_cents

RATES = {{"CA": 825, "NY": 888, "TX": 625, "OR": 0}}


def tax_rate_for(state):
    return RATES.get(state, 700)


def tax_cents(subtotal_cents, rate_bp):
    """Nonnegative tax rounds half-up to whole cents."""
{tax_line}


def tax_breakdown(lines, state):
    rate = tax_rate_for(state)
    return [(line["sku"], tax_cents(to_cents(line["price"]) * line["qty"], rate)) for line in lines]
''')
    w(root, "backend/services/pricing.py", '''
from backend.services.money import to_cents
from backend.services.tax import tax_cents, tax_rate_for
from backend.services.discounts import best_discount
from backend.services.shipping import shipping_cost


def line_total(line):
    return to_cents(line["price"]) * line["qty"]


def subtotal(lines):
    return sum(line_total(line) for line in lines)


def order_total(lines, state, coupon=None):
    base = subtotal(lines)
    discount = best_discount(lines, coupon)
    taxable = base - discount
    return taxable + tax_cents(taxable, tax_rate_for(state)) + shipping_cost(base)
''')
    w(root, "backend/services/discounts.py", '''
from backend.services.money import to_cents

COUPONS = {"WELCOME10": 10, "VIP20": 20}


def sale_price(line):
    return to_cents(line.get("sale_price", line["price"])) * line["qty"]


def apply_coupon(amount_cents, coupon):
    percent = COUPONS.get(coupon, 0)
    return amount_cents * percent // 100


def best_discount(lines, coupon=None):
    """Coupons never stack with sale prices: take whichever saves more."""
    regular = sum(to_cents(l["price"]) * l["qty"] for l in lines)
    on_sale = sum(sale_price(l) for l in lines)
    sale_savings = regular - on_sale
    coupon_savings = apply_coupon(regular, coupon) if coupon else 0
    return max(sale_savings, coupon_savings)
''')
    w(root, "backend/services/shipping.py", ('''
from backend.services.money import to_cents


def free_shipping_threshold():
    return to_cents(75)


def shipping_cost(subtotal_cents):
    return 0 if subtotal_cents {CMP} free_shipping_threshold() else to_cents(6.95)


def estimate_days(state):
    return 2 if state in ("CA", "OR") else 5
''').replace("{CMP}", ">" if ship_bug else ">="))
    w(root, "backend/services/refunds.py", '''
import datetime
from backend.services.money import to_cents
from backend.services.audit import record
from backend.services.notifications import send_refund_notice


def refund_window_open(order, today=None):
    today = today or datetime.date.today()
    return (today - order["placed"]).days <= 30


def refundable_amount(order):
    return to_cents(order["paid"]) - sum(to_cents(r) for r in order.get("refunds", []))


def issue_refund(order, amount):
    cents = to_cents(amount)
    if cents > refundable_amount(order) or not refund_window_open(order):
        raise ValueError("refund not allowed")
    record("refund", order["id"], cents)
    send_refund_notice(order["email"], cents)
    return cents
''')
    w(root, "backend/services/inventory.py", '''
STOCK = {}


def in_stock(sku, qty=1):
    return STOCK.get(sku, 0) >= qty


def reserve(sku, qty):
    if not in_stock(sku, qty):
        raise ValueError("out of stock")
    STOCK[sku] -= qty


def release(sku, qty):
    STOCK[sku] = STOCK.get(sku, 0) + qty
''')
    w(root, "backend/services/auth.py", '''
def current_user(request):
    return getattr(request, "user", None)


def require_login(request):
    user = current_user(request)
    if user is None:
        raise PermissionError("login required")
    return user


def is_admin(user):
    return bool(user and user.get("role") == "admin")
''')
    w(root, "backend/services/audit.py", '''
EVENTS = []


def record(kind, ref, amount=None):
    EVENTS.append({"kind": kind, "ref": ref, "amount": amount})


def recent_events(limit=20):
    return EVENTS[-limit:]
''')
    w(root, "backend/services/notifications.py", '''
from backend.services.money import format_price

OUTBOX = []


def send_receipt(email, total_cents):
    OUTBOX.append((email, "receipt", format_price(total_cents)))


def send_refund_notice(email, cents):
    OUTBOX.append((email, "refund", format_price(cents)))


def send_low_stock_alert(sku):
    OUTBOX.append(("ops@example.invalid", "low-stock", sku))
''')
    for model, fields in {"order": "id placed paid email lines", "user": "id email role", "product": "sku name price",
                          "cart": "user_id lines"}.items():
        names = fields.split()
        w(root, f"backend/models/{model}.py", f'''
from dataclasses import dataclass, field


@dataclass
class {model.title()}:
''' + "".join(f"    {n}: object = None\n" for n in names))
    for util in ("dates", "strings", "validation", "logging_setup", "pagination"):
        w(root, f"backend/utils/{util}.py", f'''
def {util}_helper(value):
    return value


def {util}_check(value):
    return value is not None
''')
    w(root, "backend/utils/__init__.py", "")
    w(root, "backend/app.py", '''
from backend.api import orders, cart, checkout, products, refunds, users, admin, search, health

BLUEPRINTS = [orders, cart, checkout, products, refunds, users, admin, search, health]
''')
    w(root, "backend/router.py", '''
class Router:
    def __init__(self):
        self.routes = []

    def _add(self, method, path):
        def deco(fn):
            self.routes.append((method, path, fn))
            return fn
        return deco

    def get(self, path):
        return self._add("GET", path)

    def post(self, path):
        return self._add("POST", path)

    def patch(self, path):
        return self._add("PATCH", path)

    def delete(self, path):
        return self._add("DELETE", path)


router = Router()
''')
    uses = {"orders": ("pricing", "order_total"), "cart": ("pricing", "subtotal"), "checkout": ("pricing", "order_total"),
            "products": ("money", "format_price"), "refunds": ("refunds", "issue_refund"), "users": ("auth", "current_user"),
            "admin": ("audit", "recent_events"), "search": ("money", "format_price"), "health": ("audit", "recent_events")}
    for api, routes in APIS.items():
        mod, fn = uses[api]
        body = [f"from backend.router import router\nfrom backend.services.{mod} import {fn}\nfrom backend.services.auth import require_login\n"]
        for i, (method, path) in enumerate(routes):
            handler = f"{api}_{method.lower()}_{i}"
            if api == "cart" and method == "GET":
                body.append(f'''

@router.get("{path}")
def get_cart(request):
    """Guests get {{"cart": None}}; signed-in users get their lines and totals."""
    user = getattr(request, "user", None)
    if user is None:
        return {{"cart": None}}
    lines = request.store.cart_lines(user["id"])
    return {{"cart": {{"lines": lines, "subtotal": subtotal(lines)}}}}
''')
                continue
            if api == "checkout" and method == "POST":
                body.append(f'''

@router.post("{path}")
def checkout_post(request):
    require_login(request)
    lines, state, coupon = request.json["lines"], request.json["state"], request.json.get("coupon")
    return {{"total": order_total(lines, state, coupon)}}
''')
                continue
            body.append(f'''

@router.{method.lower()}("{path}")
def {handler}(request):
    require_login(request)
    return {{"ok": True, "value": {fn}.__name__}}
''')
        w(root, f"backend/api/{api}.py", "".join(body))


def tests(root, noisy=False):
    w(root, "tests/__init__.py", "")
    w(root, "tests/test_tax.py", '''
import unittest
from backend.services.tax import tax_cents, tax_rate_for


class TaxTests(unittest.TestCase):
    def test_whole_cents(self):
        self.assertEqual(tax_cents(10_000, 825), 825)

    def test_half_cent_rounds_up(self):
        self.assertEqual(tax_cents(1_000, 825), 83)

    def test_below_half_rounds_down(self):
        self.assertEqual(tax_cents(1_001, 824), 82)

    def test_unknown_state_default(self):
        self.assertEqual(tax_rate_for("ZZ"), 700)
''')
    w(root, "tests/test_pricing.py", '''
import unittest
from backend.services.pricing import subtotal, order_total

LINES = [{"sku": "A", "price": "40.00", "qty": 1}, {"sku": "B", "price": "20.00", "qty": 2}]


class PricingTests(unittest.TestCase):
    def test_subtotal(self):
        self.assertEqual(subtotal(LINES), 8000)

    def test_total_free_shipping_no_tax_state(self):
        self.assertEqual(order_total(LINES, "OR"), 8000)
''')
    w(root, "tests/test_discounts.py", '''
import unittest
from backend.services.discounts import apply_coupon, best_discount

SALE = [{"sku": "A", "price": "100.00", "sale_price": "85.00", "qty": 1}]


class DiscountTests(unittest.TestCase):
    def test_coupon_percent(self):
        self.assertEqual(apply_coupon(10_000, "WELCOME10"), 1_000)

    def test_coupon_never_stacks_with_sale(self):
        self.assertEqual(best_discount(SALE, "WELCOME10"), 1_500)
''')
    if noisy:
        w(root, "tests/test_shipping_rules.py", '''
import unittest
from backend.services.shipping import shipping_cost


class ShippingRuleTests(unittest.TestCase):
    def test_free_shipping_at_exact_threshold(self):
        self.assertEqual(shipping_cost(7_500), 0)

    def test_paid_shipping_below_threshold(self):
        self.assertEqual(shipping_cost(7_499), 695)
''')
    for name in ("money", "shipping", "refunds", "inventory", "auth", "audit", "notifications", "api_routes", "models", "utils"):
        def body(i):
            if not noisy:
                return ""
            # Realistic chatty test output: 4 workers x 6 log lines per test.
            lines = ["        for w in range(4):"]
            for level in ("INFO", "DEBUG", "INFO", "DEBUG", "INFO", "DEBUG"):
                lines.append(f"            print(f'[{level}] {name}.worker-{{w}} request_id=req-{i:02d}{{w:03d}} "
                             f"latency_ms={{w * 7 % 90}} cache=miss')")
            return "\n".join(lines) + "\n"
        cases = "".join(f'''
    def test_{name}_case_{i:02d}(self):
{body(i)}        self.assertTrue({i} >= 0)
''' for i in range(30 if noisy else 20))
        w(root, f"tests/test_{name}.py", f"import unittest\n\n\nclass {name.title().replace('_', '')}Tests(unittest.TestCase):{cases}")


def frontend(root):
    w(root, "frontend/package.json", '{"name": "shop-frontend", "private": true, "scripts": {"dev": "vite"}}\n')
    w(root, "frontend/src/api/client.ts", '''
export async function getJson(path: string) {
  const res = await fetch(path, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${path}`);
  return res.json();
}
''')
    w(root, "frontend/src/api/endpoints.ts", '''
import { getJson } from "./client";

export const fetchCart = () => getJson("/api/cart");
export const fetchProducts = () => getJson("/api/products");
export const fetchOrders = () => getJson("/api/orders");
export const fetchMe = () => getJson("/api/users/me");
''')
    w(root, "frontend/src/hooks/useCart.ts", '''
import { useEffect, useState } from "react";
import { fetchCart } from "../api/endpoints";

export function useCart() {
  const [data, setData] = useState<any>(undefined);
  useEffect(() => { fetchCart().then(setData); }, []);
  return data;
}
''')
    w(root, "frontend/src/hooks/useCartTotals.ts", '''
import { useCart } from "./useCart";

export function useCartTotals() {
  const data = useCart();
  if (data === undefined) return { loading: true, lines: [], subtotal: 0 };
  const cart = data.cart;
  return { loading: false, lines: cart.lines, subtotal: cart.subtotal };
}
''')
    for hook in HOOKS:
        if hook in ("useCart", "useCartTotals"):
            continue
        w(root, f"frontend/src/hooks/{hook}.ts", f'''
import {{ useEffect, useState }} from "react";
import {{ getJson }} from "../api/client";

export function {hook}() {{
  const [value, setValue] = useState<any>(null);
  useEffect(() => {{ getJson("/api/{hook[3:].lower()}").then(setValue); }}, []);
  return value;
}}
''')
    w(root, "frontend/src/components/CartSummary.tsx", '''
import { useCartTotals } from "../hooks/useCartTotals";
import { CartLine } from "./CartLine";

export function CartSummary() {
  const totals = useCartTotals();
  return (
    <aside>
      {totals.lines.map((l: any) => <CartLine key={l.sku} line={l} />)}
      <strong>{(totals.subtotal / 100).toFixed(2)}</strong>
    </aside>
  );
}
''')
    for comp in COMPONENTS:
        if comp == "CartSummary":
            continue
        w(root, f"frontend/src/components/{comp}.tsx", f'''
export function {comp}(props: any) {{
  return <div className="{comp.lower()}">{{props.children}}</div>;
}}
''')
    for page in ("Home", "Cart", "Checkout", "Orders", "Account"):
        imp = "CartSummary" if page == "Cart" else "Header"
        w(root, f"frontend/src/pages/{page}Page.tsx", f'''
import {{ {imp} }} from "../components/{imp}";

export function {page}Page() {{
  return <main><{imp} /></main>;
}}
''')
    w(root, "frontend/src/main.tsx", '''
import { CartPage } from "./pages/CartPage";
import { HomePage } from "./pages/HomePage";

export const routes = { "/": HomePage, "/cart": CartPage };
''')


REVIEW_CHANGE = '''
def best_discount(lines, coupon=None):
    """Apply the sale price and then the coupon on top for extra savings."""
    regular = sum(to_cents(l["price"]) * l["qty"] for l in lines)
    on_sale = sum(sale_price(l) for l in lines)
    sale_savings = regular - on_sale
    coupon_savings = apply_coupon(on_sale, coupon) if coupon else 0
    return sale_savings + coupon_savings
'''

MEMORY_ONLY = [
    ("decision", "Refund window stays 30 days (card-network chargeback rules, legal review 2026-08). Longer goodwill returns are "
     "issued as store credit, never by changing refund_window_open", ["backend/services/refunds.py"], ["refunds", "legal"]),
]

CLAUDE_MD = (Path(__file__).resolve().parents[2] / "templates" / "CLAUDE.md").read_text(encoding="utf-8")

MEMORIES = [
    ("decision", "Coupons never stack with sale prices; best_discount takes whichever saves more (finance decision 2026-09)",
     ["backend/services/discounts.py"], ["discounts", "coupons"]),
    ("concept", "GET /api/cart returns {\"cart\": null} for guests (not logged in); frontend hooks must treat a null cart as empty",
     ["backend/api/cart.py", "frontend/src/hooks/useCart.ts"], ["cart", "guests"]),
    ("decision", "All money is integer cents; to_cents is the only place floats become cents", ["backend/services/money.py"], ["money"]),
    ("gotcha", "Tax must round half-up via round_half_up, never floor division", ["backend/services/tax.py"], ["tax", "rounding"]),
]


def run(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True,
                   env={**__import__("os").environ, "GIT_AUTHOR_NAME": "bench", "GIT_AUTHOR_EMAIL": "bench@example.invalid",
                        "GIT_COMMITTER_NAME": "bench", "GIT_COMMITTER_EMAIL": "bench@example.invalid"})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("out")
    p.add_argument("--task", required=True, choices=["browser", "review", "impact", "tests", "noisy", "memory"])
    p.add_argument("--claude-md", action="store_true", help="add the kit's recommended CLAUDE.md rules to the fixture")
    p.add_argument("--memory", action="store_true")
    a = p.parse_args()
    root = Path(a.out)
    if root.exists() and any(root.iterdir()):
        raise SystemExit(f"{root} is not empty")
    root.mkdir(parents=True, exist_ok=True)
    backend(root, tax_bug=(a.task == "tests"), ship_bug=(a.task == "noisy"))
    tests(root, noisy=(a.task == "noisy"))
    frontend(root)
    run(root, "init", "-q")
    run(root, "add", "-A")
    run(root, "commit", "-qm", "shop app")
    if a.task == "review":
        f = root / "backend/services/discounts.py"
        text = f.read_text(encoding="utf-8")
        start = text.index("def best_discount")
        f.write_bytes((text[:start] + REVIEW_CHANGE.lstrip("\n")).encode("utf-8"))
    if a.claude_md:
        (root / "CLAUDE.md").write_bytes((CLAUDE_MD).encode("utf-8"))
        run(root, "add", "CLAUDE.md")
        run(root, "commit", "-qm", "project rules")
    if a.memory:
        items = []
        memories = MEMORIES + (MEMORY_ONLY if a.task == "memory" else [])
        for i, (kind, text, files, tags) in enumerate(memories, 1):
            items.append({"id": i, "kind": kind, "text": text, "date": datetime.date.today().isoformat(), "files": files,
                          "fp": {}, "tags": tags, "links": []})
        (root / ".git" / "lean-memory.json").write_text(json.dumps({"next": len(items) + 1, "items": items}, indent=1),
                                                       encoding="utf-8")
    files = sum(1 for x in root.rglob("*") if x.is_file() and ".git" not in x.parts)
    truth = {
        "files": files,
        "browser": {"root_cause_file": "frontend/src/hooks/useCartTotals.ts", "reason": "cart is null for guests"},
        "review": {"violates": "coupons never stack with sale prices", "callers": ["backend/services/pricing.py"],
                   "tests": ["tests/test_discounts.py", "tests/test_pricing.py"]},
        "impact": {"callers_of_to_cents": sorted(["backend/services/tax.py", "backend/services/pricing.py",
                                                  "backend/services/discounts.py", "backend/services/shipping.py",
                                                  "backend/services/refunds.py"]),
                   "tests": sorted(["tests/test_tax.py", "tests/test_pricing.py", "tests/test_discounts.py"])},
        "tests": {"failing": "tests/test_tax.py::test_half_cent_rounds_up", "fix_file": "backend/services/tax.py"},
        "memory": {"request": "extend the refund window from 30 to 60 days",
                   "memory_only_fact": "refund window stays 30 days; goodwill returns go through store credit",
                   "pass": "does not change refund_window_open's 30-day limit; cites the recorded decision and proposes store credit or asks",
                   "fail": "changes 30 to 60 without mentioning the recorded decision"},
        "noisy": {"failing": "tests/test_shipping_rules.py::test_free_shipping_at_exact_threshold",
                  "fix_file": "backend/services/shipping.py", "fix": "use >= for the free-shipping threshold"},
    }
    print(json.dumps(truth))


if __name__ == "__main__":
    main()
