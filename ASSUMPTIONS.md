# Assumptions

## Assumption 1: EUR/USD FX rate date
- **What I assumed:** 31 December 2022 was a Saturday, so the ECB did not publish a rate. I use the ECB euro reference rate from **30 December 2022 (Friday)**, the last business day before the valuation date. The rate is **EUR/USD 1.0666** (ECB published: 1 EUR = 1.0666 USD).
- **Why:** ECB reference rates are only published on TARGET2 business days. Standard market practice is to use the last available rate before or on the valuation date. CVP used the same convention in Q3 (rate on 30 Sep 2022, a Friday).
- **What would change if wrong:** If a different date's rate were used (e.g., 2 Jan 2023, the next business day), Ember Retail GmbH's USD fair value and total investments would shift, changing the NAV. The difference would be roughly proportional to the one-day EUR/USD move.

## Assumption 2: Company with no mark yet (Ionmere Materials Ltd)
- **What I assumed:** Ionmere Materials Ltd was acquired on 15 December 2022 and CVP notes it has not been valued yet (first valuation at Q1 2023). I carry it at **cost (USD 14,000,000)** as its fair value at 31 December 2022.
- **Why:** Common fund accounting practice is to carry a recent purchase at cost until the first independent valuation is available. The purchase price is the best estimate of fair value when no market-based valuation exists and the holding period is very short (16 days).
- **What would change if wrong:** If excluded from the NAV, investments at fair value would be understated by USD 14,000,000 and the NAV would drop by the same amount. If a different value were used, the NAV would shift accordingly.

## Assumption 3: Materiality threshold for mark changes
- **What I assumed:** A mark change is "material" (rule R1) if the fair value changed by more than **15%** from Q3 to Q4, measured in the company's **local currency** (not USD).
- **Why:** The brief says many funds use 10–25%. I chose 15% as a middle-ground that catches genuinely significant moves without over-flagging. I measure in local currency because a move caused solely by FX is not a change in the company's underlying value—it is an FX effect. CVP states fair values in local currency, so comparing in the same currency isolates operational performance.
- **What would change if wrong:** A lower threshold (e.g., 10%) would flag more companies, possibly including ones whose changes are within normal quarter-to-quarter drift. A higher threshold (e.g., 25%) would miss companies with meaningful but not extreme valuation moves.
