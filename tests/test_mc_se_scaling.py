from QuantLib import Settings, Date, Period, Months, Option as QLOption
from lawson_quant_library.market import MarketParams
from lawson_quant_library.models import MonteCarloModel
from lawson_quant_library.instruments import Option

def test_mc_se_scales_like_one_over_sqrt_n():
    Settings.instance().evaluationDate = Date.todaysDate()
    mat = Date.todaysDate() + Period(6, Months)
    opt = Option(strike=100, maturity_date=mat, option_type=QLOption.Call)

    mkt = MarketParams(spot=100, risk_free_rate=0.03, div_yield=0.01, vol=0.20)
    mc  = MonteCarloModel(spot=100, risk_free_rate=0.03, volatility=0.20, div_yield=0.01)

    N1, N2 = 20_000, 80_000  # N2 = 4 * N1 → SE should drop ~ by 1/2
    _, se1 = mc.price_and_se(opt, num_paths=N1, seed=7,  antithetic=True)
    _, se2 = mc.price_and_se(opt, num_paths=N2, seed=11, antithetic=True)

    # allow some slack (10–20%) because SE itself is random
    assert se2 <= 0.55 * se1, f"Expected ~half: se1={se1:.6f}, se2={se2:.6f}"