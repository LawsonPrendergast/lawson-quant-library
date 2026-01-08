from QuantLib import Settings, Date, Period, Months, Option as QLOption
from lawson_quant_library.market import MarketParams
from lawson_quant_library.models import BlackScholesModel, MonteCarloModel
from lawson_quant_library.instruments import Option

Settings.instance().evaluationDate = Date.todaysDate()
mat = Date.todaysDate() + Period(6, Months)
opt = Option(strike=100, maturity_date=mat, option_type=QLOption.Call)

mkt = MarketParams(spot=100, risk_free_rate=0.03, div_yield=0.01, vol=0.20)
bs  = BlackScholesModel(market=mkt)
mc  = MonteCarloModel(spot=100, risk_free_rate=0.03, volatility=0.20, div_yield=0.01)

p_bs = bs.price(opt)
p_mc = mc.price(opt, num_paths=100_000, seed=42, antithetic=True)
print("BS:", p_bs, "MC:", p_mc, "diff:", abs(p_bs - p_mc))