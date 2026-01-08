from QuantLib import Settings, Date, Period, Months, Option as QLOption
from lawson_quant_library.instruments import Option
from lawson_quant_library.market import MarketParams
from lawson_quant_library.models import BlackScholesModel, MonteCarloModel

def test_same_option_two_models():

    Settings.instance().evaluationDate = Date.todaysDate()

    mat = Date.todaysDate() + Period(6, Months)
    opt = Option(strike=100, maturity_date=mat, option_type=QLOption.Call)

    mkt = MarketParams(spot=100, risk_free_rate=0.03, div_yield=0.01, vol=0.20)
    bs = BlackScholesModel(market=mkt)
    mc = MonteCarloModel(spot=100, risk_free_rate=0.03, volatility=0.20, div_yield=0.01)

    p_bs = bs.price(opt)
    p_mc, se = mc.price_and_se(opt, num_paths=50_000, seed=42, antithetic=True)

    assert abs(p_mc - p_bs) <= 3*se + 0.01
