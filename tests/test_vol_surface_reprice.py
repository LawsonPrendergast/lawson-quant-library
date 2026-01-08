from QuantLib import Settings, Date, Period, Months, Option as QLOption, BlackVolTermStructure
import QuantLib as ql 
from lawson_quant_library.market import MarketParams
from lawson_quant_library.models import BlackScholesModel
from lawson_quant_library.instruments import Option
from lawson_quant_library.vol_surface import read_chain_csv, build_vol_surface

def test_reprice_with_surface_handle():

    Settings.instance().evaluationDate = Date.todaysDate()
    mat = Date.todaysDate() + Period(6, Months)

    flat_mkt = MarketParams(spot=100, risk_free_rate=0.03, div_yield=0.01, vol=0.20)
    opt = Option(strike=100, maturity_date=mat, option_type=QLOption.Call)

    flat_bs = BlackScholesModel(market=flat_mkt)
    flat_price = flat_bs.price(opt)

    chain = read_chain_csv("option_chain.csv")
    surface = build_vol_surface(chain)

    surf_handle = ql.BlackVolTermStructureHandle(surface)
    surf_mkt = MarketParams(spot=100, risk_free_rate=0.03, div_yield=0.01, vol_handle=surf_handle)

    surf_bs = BlackScholesModel(market=surf_mkt)
    surf_price = surf_bs.price(opt)

    assert abs(surf_price - flat_price) > 1e-6

