# tests/test_montecarlo_accuracy.py
from QuantLib import Settings, Date, Period, Months, Option as QLOption
from lawson_quant_library.market import MarketParams
from lawson_quant_library.models import BlackScholesModel, MonteCarloModel
from lawson_quant_library.instruments import Option

def test_mc_converges_to_bs():
    # Set "today"
    Settings.instance().evaluationDate = Date.todaysDate()
    mat = Date.todaysDate() + Period(6, Months)
    opt = Option(strike=100, maturity_date=mat, option_type=QLOption.Call)

    # Market + models
    mkt = MarketParams(spot=100, risk_free_rate=0.03, div_yield=0.01, vol=0.20)
    bs  = BlackScholesModel(market=mkt)
    mc  = MonteCarloModel(spot=100, risk_free_rate=0.03, volatility=0.20, div_yield=0.01)

    p_bs = bs.price(opt)

    # Try increasing N; require MC to be within ~3 SE of BS
    Ns = [5_000, 20_000, 80_000]
    diffs = []
    for N in Ns:
        p_mc, se = mc.price_and_se(opt, num_paths=N, seed=42, antithetic=True)
        diff = abs(p_mc - p_bs)
        diffs.append(diff)
        tol = 3.0 * se + 0.005  # 3σ plus a tiny absolute floor
        assert diff <= tol, f"N={N}: diff={diff:.5f} > tol={tol:.5f} (SE={se:.5f})"