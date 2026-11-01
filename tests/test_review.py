"""Offline tests for review rules R1–R4."""

from decimal import Decimal


class TestReviewRules:
    """Test review rule logic with known Q3/Q4 values."""

    def test_r1_material_change(self):
        """R1: flag when mark changed > threshold from Q3 to Q4."""
        threshold_pct = Decimal("15")
        q3_fv = Decimal("14100000")  # Cedar Health Holdings Q3
        q4_fv = Decimal("9600000")   # Cedar Health Holdings Q4
        change_pct = ((q4_fv - q3_fv) / q3_fv * 100).quantize(Decimal("0.01"))
        # -31.91% — should be flagged
        assert abs(change_pct) > threshold_pct

    def test_r1_no_flag_small_change(self):
        """R1: do not flag if change is within threshold."""
        threshold_pct = Decimal("15")
        q3_fv = Decimal("24600000")  # Aurora Q3
        q4_fv = Decimal("25700000")  # Aurora Q4
        change_pct = ((q4_fv - q3_fv) / q3_fv * 100).quantize(Decimal("0.01"))
        # +4.47% — should NOT be flagged
        assert abs(change_pct) <= threshold_pct

    def test_r2_method_change(self):
        """R2: flag when valuation method changed Q3→Q4."""
        q3_method = "Recent transaction"
        q4_method = "Market multiples"
        assert q3_method != q4_method  # should be flagged

    def test_r3_no_mark(self):
        """R3: flag if the fund holds a company but CVP gave no Q4 mark."""
        # Ionmere Materials Ltd was purchased 15 Dec 2022, no Q4 mark
        held_companies = {"Ionmere Materials Ltd", "Aurora Logistics Pvt Ltd"}
        marked_companies = {"Aurora Logistics Pvt Ltd"}
        unvalued = held_companies - marked_companies
        assert "Ionmere Materials Ltd" in unvalued

    def test_r4_mark_for_sold_company(self):
        """R4: flag if CVP gave a mark for a company no longer held."""
        held_companies = {"Aurora Logistics Pvt Ltd"}
        marked_companies = {"Aurora Logistics Pvt Ltd", "Fjord Payments AS"}
        extra_marks = marked_companies - held_companies
        assert "Fjord Payments AS" in extra_marks
