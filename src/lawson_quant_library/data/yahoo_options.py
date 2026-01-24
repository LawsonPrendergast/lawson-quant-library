import pandas as pd
import yfinance as yf

class YahooOptionsData:
    '''
    Data adaptoor for pulling option chain data from Yahoo Finance.

    This class is focused on data retrieval only
    '''

    def __init__(self, ticker: str):
        self.ticker = ticker
        self._yf = yf.Ticker(ticker)

    def expiries(self) -> list[str]:
        t = yf.Ticker(self.ticker)
        return list(t.options)
    
    def option_chain(self, expiry: str) -> dict[str, pd.DataFrame]:
        chain = self._yf.option_chain(expiry)
        return{
            "calls": chain.calls,
            "puts": chain.puts,
        }
    
    def normalize_chain(df, expiry, option_type):
        df = df.copy()

        df['expiry'] = pd.to_datetime(expiry)
        df['type'] = option_type
        
        # mid price

        if 'bid' in df.columns and 'ask' in df.columns:
            df['mid'] = (df['bid'] + df['ask']) / 2.0
        else:
            df['mid'] = df['lastPrice']

        return df
    
        
    