from QuantLib import Settings, Date, Period, Months, Option as QLOption
from lawson_quant_library.market import MarketParams
from lawson_quant_library.models import BlackScholesModel
from lawson_quant_library.instruments import Option

Settings.instance().evaluationDate = Date.todaysDate()
mat = Date.todaysDate() + Period(6, Months)
today = Settings.instance().evaluationDate
opt = Option(strike=100, maturity_date=mat, option_type=QLOption.Call)
mkt = MarketParams(spot=100, risk_free_rate=0.03, div_yield=0.00, vol=0.20)
bs = BlackScholesModel(market=mkt)
p0 = bs.price(opt)
Settings.instance().evaluationDate = today + Period(3, Months)
p1 = bs.price(opt)
print(f"before move:{p0:.4f} After +3M: {p1:.4f}")


