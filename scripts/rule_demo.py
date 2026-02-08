import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pump
import json

# Variant: S2, TA>0.5, Nsmall, slope_pos

def variant_find_buy_signal(trade_data, start_index, creation_time):
    if start_index < 0 or start_index >= len(trade_data):
        return None
    rec = trade_data[start_index]
    # ensure numeric fields
    try:
        nowsol = float(rec.get('nowsol', 0))
        tradeamount = float(rec.get('tradeamount', 0))
    except Exception:
        return None

    # Compute sum_last_5 and slope_5 on-the-fly from trade_data prior to start_index
    # sum_last_5: sum of tradeamount of up to 5 previous trades
    # slope_5: simple linear slope of nowsol over up to 5 previous points (least-squares slope)
    vals_amount = []
    vals_nowsol = []
    # collect up to 5 records before start_index (excluding current)
    for j in range(max(0, start_index-5), start_index):
        try:
            vals_amount.append(float(trade_data[j].get('tradeamount', 0)))
            vals_nowsol.append(float(trade_data[j].get('nowsol', 0)))
        except Exception:
            vals_amount.append(0.0)
            vals_nowsol.append(0.0)

    sum_last_5 = sum(vals_amount)

    # slope: if fewer than 2 points, slope = 0
    if len(vals_nowsol) < 2:
        slope_5 = 0.0
    else:
        # x = indices 0..n-1, y = vals_nowsol
        n = len(vals_nowsol)
        x_mean = (n-1)/2.0
        y_mean = sum(vals_nowsol)/n
        num = sum((i - x_mean)*(y - y_mean) for i, y in enumerate(vals_nowsol))
        den = sum((i - x_mean)**2 for i in range(n))
        slope_5 = num/den if den != 0 else 0.0

    if not (5.0 < nowsol < 13.0):
        return None
    if not (abs(tradeamount) > 0.5):
        return None
    if not (abs(sum_last_5) < 5.0):
        return None
    if not (slope_5 > 0):
        return None
    return start_index

# monkey patch
pump.find_buy_signal = variant_find_buy_signal

start=time.time()
print('Running pump.run_backtest() with variant S2|TA>0.5|Nsmall|slope_pos')
pump.run_backtest()
end=time.time()
print('Elapsed:', end-start)
