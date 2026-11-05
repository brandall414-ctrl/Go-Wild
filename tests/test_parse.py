import unittest
from pathlib import Path

from gowild import parse
from gowild.watch import build_alert

FIX = Path(__file__).parent / "fixtures"


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.deals = parse.deals_offers((FIX / "deals.html").read_text())
        self.terms = parse.terms_prices((FIX / "terms.html").read_text())
        self.feed = parse.feed_items((FIX / "feed.xml").read_text())

    def test_headline_price_found(self):
        self.assertTrue(any("$249" in x for x in self.deals))

    def test_hidden_old_promos_ignored(self):
        # The $25 voucher promo only exists inside an HTML comment on this page.
        self.assertFalse(any("$25 Frontier Airlines voucher" in x for x in self.deals))

    def test_fee_boilerplate_ignored(self):
        self.assertFalse(any("$15.40" in x or "Peak Day Charge" in x for x in self.deals))

    def test_annual_prices_in_terms(self):
        self.assertTrue(any("$699" in x for x in self.terms))

    def test_feed_has_gowild_posts(self):
        self.assertTrue(any("Annual Pass" in i["title"] for i in self.feed))

    def test_alert_on_new_price(self):
        old = {"deals": self.deals, "terms": self.terms, "feed": self.feed}
        new = dict(old, deals=self.deals + ["Get your GoWild Annual Pass for $299 today!"])
        subject, body = build_alert(old, new)
        self.assertTrue(subject.startswith("[ANNUAL PASS]"))
        self.assertIn("$299", body)

    def test_no_alert_when_unchanged(self):
        old = {"deals": self.deals, "terms": self.terms, "feed": self.feed}
        self.assertIsNone(build_alert(old, dict(old)))


if __name__ == "__main__":
    unittest.main()
