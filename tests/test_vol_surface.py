from lawson_quant_library.vol_surface import read_chain_csv, build_vol_surface
from QuantLib import Settings, Actual365Fixed

chain = read_chain_csv("option_chain.csv")
surface = build_vol_surface(chain)

# Compute T to the last expiry in the chain (always in-range)
dates = sorted({d for (d, _, _) in chain})
today = Settings.instance().evaluationDate
dc = Actual365Fixed()
T_last = dc.yearFraction(today, dates[-1])

print("Test vol (T_last, K=100):", surface.blackVol(T_last, 100))