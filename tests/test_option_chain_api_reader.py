import pandas as pd
from lawson_quant_library.data import OptionChainReader

def test_from_api_minimal_schema():
    df = OptionChainReader.from_api('AAPL')
    assert set(['expiry', 'strike', 'type', 'implied_vol']).issubset(df.columns)
    assert df['type'].isin(['C', 'P']).all()
    assert df['implied_vol'].dtype.kind in ('f', 'i')