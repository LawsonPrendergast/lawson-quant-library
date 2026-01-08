from lawson_quant_library.market import MarketParams
from pathlib import Path

def test_load_from_csv():
    csv_path = Path(__file__).with_name("market_snapshot.csv")
    mkt = MarketParams(spot=100, risk_free_rate=0.03, div_yield=0.0, vol=0.20)
    mkt.load_from_csv(str(csv_path))
    assert mkt.spot == 102.5
    assert mkt.r == 0.035
    assert mkt.q == 0.005
    assert mkt.vol == 0.22