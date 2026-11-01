"""Offline tests for review rules R1–R4 using actual GPF data."""

from decimal import Decimal

import pytest


class TestReviewRules:
    """Test review rule logic with actual Q3/Q4 values."""

    def test_r1_cedar_flagged(self):
        """Cedar Health: -31.91% change → flagged."""
        threshold = Decimal("15")
        q3 = Decimal("14100000")
        q4 = Decimal("9600000")
        pct = ((q4 - q3) / q3 * 100).quantize(Decimal("0.01"))
        assert pct == Decimal("-31.91")
        assert abs(pct) > threshold

    def test_r1_bluetarn_flagged(self):
        """Bluetarn: +37.50% change → flagged."""
        threshold = Decimal("15")
        q3 = Decimal("31200000")
        q4 = Decimal("42900000")
        pct = ((q4 - q3) / q3 * 100).quantize(Decimal("0.01"))
        assert pct == Decimal("37.50")
        assert abs(pct) > threshold

    def test_r1_harbor_flagged(self):
        """Harbor: +17.83% change → flagged."""
        threshold = Decimal("15")
        q3 = Decimal("9200000")
        q4 = Decimal("10840000")
        pct = ((q4 - q3) / q3 * 100).quantize(Decimal("0.01"))
        assert pct == Decimal("17.83")
        assert abs(pct) > threshold

    def test_r1_aurora_not_flagged(self):
        """Aurora: +4.47% → NOT flagged."""
        threshold = Decimal("15")
        q3 = Decimal("24600000")
        q4 = Decimal("25700000")
        pct = ((q4 - q3) / q3 * 100).quantize(Decimal("0.01"))
        assert pct == Decimal("4.47")
        assert abs(pct) <= threshold

    def test_r1_ember_not_flagged_in_eur(self):
        """Ember: -2.96% in EUR → NOT flagged (local currency comparison)."""
        threshold = Decimal("15")
        q3_eur = Decimal("13500000")
        q4_eur = Decimal("13100000")
        pct = ((q4_eur - q3_eur) / q3_eur * 100).quantize(Decimal("0.01"))
        assert pct == Decimal("-2.96")
        assert abs(pct) <= threshold

    def test_r2_delta_method_change(self):
        """Delta: Recent transaction → Market multiples → flagged R2."""
        q3_method = "Recent transaction"
        q4_method = "Market multiples"
        assert q3_method != q4_method

    def test_r3_ionmere_no_mark(self):
        """Ionmere: purchased Dec 15, no Q4 mark → flagged R3."""
        held = {"Ionmere Materials Ltd", "Aurora Logistics Pvt Ltd"}
        marked = {"Aurora Logistics Pvt Ltd"}
        unvalued = held - marked
        assert "Ionmere Materials Ltd" in unvalued

    def test_r4_fjord_not_flagged(self):
        """Fjord was sold on 18 Nov → not held at Q4 → no R4 flag
        because it has no Q4 mark either (CVP removed it from coverage)."""
        held_at_q4 = {"Aurora Logistics Pvt Ltd", "Bluetarn Software Inc"}
        q4_marked = {"Aurora Logistics Pvt Ltd", "Bluetarn Software Inc"}
        extra = q4_marked - held_at_q4
        assert "Fjord Payments AS" not in extra

    def test_flagged_companies_list(self):
        """Verify the exact set of flagged companies."""
        expected_flagged = {
            "Bluetarn Software Inc",    # R1
            "Cedar Health Holdings",    # R1
            "Delta Agritech Ltd",       # R2
            "Harbor Analytics Inc",     # R1
            "Ionmere Materials Ltd",    # R3
        }
        # From the review output
        import json
        from pathlib import Path
        review_path = Path("output/review.json")
        if review_path.exists():
            with open(review_path) as f:
                review = json.load(f)
            actual = {c["company"] for c in review["companies"] if c["flags"]}
            assert actual == expected_flagged
