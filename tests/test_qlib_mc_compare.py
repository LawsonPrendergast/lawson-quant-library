from QuantLib import (
    Settings, Date, Period, Months, Actual365Fixed, PlainVanillaPayoff,
    EuropeanExercise, BlackScholesMertonProcess, VanillaOption,
    SimpleQuote, QuoteHandle, YieldTermStructureHandle, FlatForward,
    BlackVolTermStructureHandle, BlackConstantVol, MCEuropeanEngine, Option as QLOption, NullCalendar
)
from lawson_quant_library.instruments import Option
from lawson_quant_library.models import MonteCarloModel

def test_qlib_mc_matches_our_mc_within_se():
    #Valuation Date
    today = Date.todaysDate()
    Settings.instance().evaluationDate = today
    mat = today + Period(6, Months)

    #Common market inputs
    day_count = Actual365Fixed()
    S0 = 100.0; r= 0.03; q = 0.00; vol = 0.20
    strike = 100.0
    N = 20000; seed = 42

    # QuantLib handles
    spot_q = SimpleQuote(S0)
    spot_h = QuoteHandle(spot_q)
    r_h = YieldTermStructureHandle(FlatForward(today, r, day_count))
    q_h = YieldTermStructureHandle(FlatForward(today, q, day_count))
    vol_h = BlackVolTermStructureHandle(BlackConstantVol(today, NullCalendar(), vol, day_count))

    # QL process + instrument
    process = BlackScholesMertonProcess(spot_h, q_h, r_h, vol_h)
    payoff = PlainVanillaPayoff(QLOption.Call, strike)
    exercise = EuropeanExercise(mat)
    ql_opt = VanillaOption(payoff, exercise)
    ql_opt.setPricingEngine(MCEuropeanEngine(process, "pseudorandom", timeSteps=1, requiredSamples=N, seed=seed))
    ql_mc_price = ql_opt.NPV()

    #My MC
    inst = Option(strike=strike, maturity_date=mat, option_type=QLOption.Call)
    my_mc = MonteCarloModel(spot=S0, risk_free_rate=r, volatility=vol, div_yield=q)
    my_price, my_se = my_mc.price_and_se(inst, num_paths=N, seed=seed, antithetic=True)

    assert abs(my_price - ql_mc_price) <= 3.0 * my_se +1e-3