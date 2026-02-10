import sys, os, time
import itertools
import copy
import io
import contextlib
import concurrent.futures
import multiprocessing
import shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pump
import json
from typing import Dict, List, Optional, Tuple

STRATEGY_CONFIG = pump.STRATEGY_CONFIG

# =============================================================================
# 参数搜索空间定义 (根据要求初始化多个分组)
# =============================================================================
PARAM_SEARCH_SPACE = {
    'TIME_FROM_CREATION_MINUTES': [3],
    'NOWSOL_RANGE': [(5, 35), (5, 15)],
    'TRADE_AMOUNT_RANGE': [(0.3, 2.0)],
    'TIME_DIFF_CHECK_MODE': ['debug'],
    'FILTERED_TRADES_MIN_AMOUNT': [0.05, 0.1, 0.2],
    'FILTERED_TRADES_COUNT': [7, 10],
    'FILTERED_TRADES_SUM_RANGE': [(-6.0, -2.0), (-4.0, -2.0)],
    'TRADE_TYPE': ['buy'],
    'MAX_AMOUNT_CHECK_MODE': ['debug'],
    'PRICE_VOLATILITY_CHECK_MODE': ['debug'],
    'TIME_VOLATILITY_CHECK_MODE': ['debug'],
    'AMOUNT_VOLATILITY_CHECK_MODE': ['debug'],
    'PRICE_RATIO_CHECK_MODE': ['debug'],
    'SELL_COUNT_CHECK_MODE': ['debug'],
    'BUY_COUNT_CHECK_MODE': ['debug'],
}

# =============================================================================
# 筛选阈值
# =============================================================================
# Step3 筛选阈值 (总盈利数>500, 总盈利>2SOL, 胜率>35%, 平均盈利率>0.5%)
FILTER_THRESHOLDS = {
    'MIN_PROFITABLE_TRADES': 500,
    'MIN_TOTAL_PROFIT_SOL': 2.0,
    'MIN_WIN_RATE': 0.35,
    'MIN_AVG_PROFIT_RATE': 0.005,
}

# =============================================================================
# 固定的基础配置模板
# =============================================================================
BASE_BUY_CONFIG = {
    'TRADE_AMOUNT_RANGE': (0.3, 2.0),
    'TIME_DIFF_CHECK_MODE': 'debug',
    'TIME_DIFF_FROM_LAST_TRADE_RANGE': (2000, 50000),
    'TIME_DIFF_BUCKETS': [0, 500, 1000, 2000, 3000, 5000, 10000, 20000, 50000],
    'TRADE_TYPE': 'buy',
    'MAX_AMOUNT_CHECK_MODE': 'debug',
    'MAX_AMOUNT_MIN_THRESHOLD': 0.05,
    'MAX_AMOUNT_LOOKBACK_COUNT': 15,
    'VOLATILITY_LOOKBACK_COUNT': 15,
    'VOLATILITY_MIN_AMOUNT': 0.1,
    'PRICE_VOLATILITY_CHECK_MODE': 'debug',
    'PRICE_VOLATILITY_RANGE': (0.0, 1.0),
    'PRICE_VOLATILITY_BUCKETS': [0.0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0],
    'TIME_VOLATILITY_CHECK_MODE': 'debug',
    'TIME_VOLATILITY_RANGE': (0.0, 10.0),
    'TIME_VOLATILITY_BUCKETS': [0.0, 0.1, 0.2, 0.5, 0.7, 1.0, 1.5, 2.0, 5.0, 10.0],
    'AMOUNT_VOLATILITY_CHECK_MODE': 'debug',
    'AMOUNT_VOLATILITY_RANGE': (0.0, 5.0),
    'AMOUNT_VOLATILITY_BUCKETS': [0.0, 0.2, 0.5, 0.7, 1.0, 1.5, 2.0, 3.0, 5.0],
    'PRICE_RATIO_CHECK_MODE': 'debug',
    'PRICE_RATIO_LOOKBACK_COUNT': 10,
    'PRICE_RATIO_RANGE': (0.0, 3.0),
    'PRICE_RATIO_BUCKETS': [0.0, 1.0, 2.0, 3.0, 5.0, 10.0, 20.0, 50.0],
    'BUY_COUNT_CHECK_MODE': 'debug',
    'BUY_COUNT_LOOKBACK_COUNT': 15,
    'BUY_COUNT_MIN': 5,
    'BUY_COUNT_BUCKETS': [0, 2, 4, 6, 8, 10, 12, 15],
    'SELL_COUNT_CHECK_MODE': 'debug',
    'SELL_COUNT_LOOKBACK_COUNT': 15,
    'SELL_COUNT_MIN': 3,
    'SELL_COUNT_BUCKETS': [0, 2, 4, 6, 8, 10, 12, 15],
    'LARGE_TRADE_RATIO_CHECK_MODE': 'debug',
    'LARGE_TRADE_RATIO_LOOKBACK': 20,
    'LARGE_TRADE_THRESHOLD': 1.0,
    'LARGE_TRADE_RATIO_RANGE': (0.0, 0.1),
    'LARGE_TRADE_RATIO_BUCKETS': [0.0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0],
    'SMALL_TRADE_RATIO_CHECK_MODE': 'debug',
    'SMALL_TRADE_RATIO_LOOKBACK': 20,
    'SMALL_TRADE_THRESHOLD': 0.1,
    'SMALL_TRADE_RATIO_RANGE': (0.0, 0.3),
    'SMALL_TRADE_RATIO_BUCKETS': [0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0],
    'CONSECUTIVE_BUY_CHECK_MODE': 'debug',
    'CONSECUTIVE_BUY_THRESHOLD': 0.3,
    'CONSECUTIVE_BUY_MIN': 3,
    'CONSECUTIVE_BUY_BUCKETS': [0, 1, 2, 3, 4, 5, 7, 10],
    'CONSECUTIVE_SELL_CHECK_MODE': 'debug',
    'CONSECUTIVE_SELL_THRESHOLD': 0.3,
    'CONSECUTIVE_SELL_MAX': 2,
    'CONSECUTIVE_SELL_BUCKETS': [0, 1, 2, 3, 4, 5, 7, 10],
}

SELL_CONDITIONS_CONFIG = {
    'MAX_NOWSOL_SELL': 70.0,
    'LOSS_PERCENTAGE': 0.05,
    'LOOKBACK_TRADES_FOR_MIN_PRICE': 7,
    'RETRACEMENT_LOW_PROFIT': 0.05,
    'RETRACEMENT_HIGH_PROFIT': 0.05,
    'HIGH_PROFIT_THRESHOLD': 0.30,
    'MAX_HOLD_TIME_SECONDS': 400,
    'QUIET_PERIOD_ENABLED': True,
    'QUIET_PERIOD_SECONDS': 40,
    'QUIET_PERIOD_MIN_AMOUNT': 0.5,
}

# =============================================================================
# 当前活跃的 BUY_CONDITIONS_CONFIG（会在每次回测前被更新）
# =============================================================================
BUY_CONDITIONS_CONFIG = {}

# debug指标不再在find_buy_signal中缓存，而是在wrapped_backtest_mint中通过buy_trigger_index重新计算


# =============================================================================
# 辅助计算函数
# =============================================================================
def is_max_amount_in_recent_trades(trade_data, current_index, current_amount, min_threshold, lookback_count):
    filtered_amounts = []
    for i in range(current_index - 1, -1, -1):
        try:
            amount = abs(float(trade_data[i].get('tradeamount', 0)))
            if amount >= min_threshold:
                filtered_amounts.append(amount)
                if len(filtered_amounts) >= lookback_count:
                    break
        except (TypeError, ValueError):
            continue
    if not filtered_amounts:
        return True
    return current_amount > max(filtered_amounts)


def get_filtered_trades_sum(trade_data, current_index, min_amount, count):
    filtered_amounts = []
    for i in range(current_index - 1, -1, -1):
        try:
            amount = float(trade_data[i].get('tradeamount', 0))
            if abs(amount) >= min_amount:
                filtered_amounts.append(amount)
                if len(filtered_amounts) >= count:
                    break
        except (TypeError, ValueError):
            continue
    if len(filtered_amounts) < count:
        return None
    return sum(filtered_amounts)


def calculate_volatility(values):
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    if mean == 0:
        return 0.0
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    std_dev = variance ** 0.5
    return std_dev / abs(mean)


def get_recent_trades_volatility(trade_data, current_index, lookback_count, min_amount, volatility_type):
    prices = []
    time_intervals = []
    amounts = []
    prev_time = None
    valid_count = 0
    for i in range(current_index - 1, -1, -1):
        if valid_count >= lookback_count:
            break
        try:
            amount = abs(float(trade_data[i].get('tradeamount', 0)))
            if amount < min_amount:
                continue
            valid_count += 1
            if volatility_type in ('price', 'all'):
                price = float(trade_data[i].get('price', 0))
                if price > 0:
                    prices.append(price)
            if volatility_type in ('time', 'all'):
                tradetime = float(trade_data[i].get('tradetime', 0))
                if tradetime > 0:
                    if prev_time is not None:
                        time_intervals.append(prev_time - tradetime)
                    prev_time = tradetime
            if volatility_type in ('amount', 'all'):
                amounts.append(amount)
        except (TypeError, ValueError):
            continue
    price_volatility = calculate_volatility(prices) if len(prices) >= 2 else None
    time_volatility = calculate_volatility(time_intervals) if len(time_intervals) >= 2 else None
    amount_volatility = calculate_volatility(amounts) if len(amounts) >= 2 else None
    return price_volatility, time_volatility, amount_volatility


def get_price_ratio_to_min(trade_data, current_index, current_price, lookback_count):
    prices = []
    count = 0
    for i in range(current_index - 1, -1, -1):
        if count >= lookback_count:
            break
        try:
            price = float(trade_data[i].get('price', 0))
            if price > 0:
                prices.append(price)
                count += 1
        except (TypeError, ValueError):
            continue
    if not prices:
        return None
    min_price = min(prices)
    if min_price <= 0:
        return None
    return (current_price / min_price - 1) * 100


def get_buy_sell_count(trade_data, current_index, lookback_count):
    buy_count = 0
    sell_count = 0
    count = 0
    for i in range(current_index - 1, -1, -1):
        if count >= lookback_count:
            break
        try:
            tradeamount = float(trade_data[i].get('tradeamount', 0))
            if tradeamount > 0:
                buy_count += 1
            elif tradeamount < 0:
                sell_count += 1
            count += 1
        except (TypeError, ValueError):
            continue
    return buy_count, sell_count


def get_large_small_trade_ratio(trade_data, current_index, lookback_count, large_threshold, small_threshold):
    large_count = 0
    small_count = 0
    total_count = 0
    for i in range(current_index - 1, -1, -1):
        if total_count >= lookback_count:
            break
        try:
            abs_amount = abs(float(trade_data[i].get('tradeamount', 0)))
            if abs_amount >= large_threshold:
                large_count += 1
            if abs_amount < small_threshold:
                small_count += 1
            total_count += 1
        except (TypeError, ValueError):
            continue
    if total_count == 0:
        return 0.0, 0.0
    return large_count / total_count, small_count / total_count


def get_consecutive_buy_sell_count(trade_data, current_index, buy_threshold, sell_threshold):
    consecutive_buy = 0
    consecutive_sell = 0
    for i in range(current_index - 1, -1, -1):
        try:
            tradeamount = float(trade_data[i].get('tradeamount', 0))
            abs_amount = abs(tradeamount)
            if tradeamount > 0 and abs_amount >= buy_threshold:
                consecutive_buy += 1
            else:
                break
        except (TypeError, ValueError):
            break
    for i in range(current_index - 1, -1, -1):
        try:
            tradeamount = float(trade_data[i].get('tradeamount', 0))
            abs_amount = abs(tradeamount)
            if tradeamount < 0 and abs_amount >= sell_threshold:
                consecutive_sell += 1
            else:
                break
        except (TypeError, ValueError):
            break
    return consecutive_buy, consecutive_sell


# =============================================================================
# 买入信号函数
# =============================================================================
def variant_find_buy_signal(trade_data, start_index, creation_time):
    if start_index < 0 or start_index >= len(trade_data):
        return None
    rec = trade_data[start_index]
    try:
        nowsol = float(rec.get('nowsol', 0))
        tradeamount = float(rec.get('tradeamount', 0))
        tradetime = int(rec.get('tradetime', 0))
    except (TypeError, ValueError):
        return None

    # 条件1: 距离创币时间
    time_diff_seconds = (tradetime - creation_time) / 1000
    time_diff_minutes = time_diff_seconds / 60
    if time_diff_minutes < BUY_CONDITIONS_CONFIG['TIME_FROM_CREATION_MINUTES']:
        return None

    # 条件2: 市值范围
    nowsol_min, nowsol_max = BUY_CONDITIONS_CONFIG['NOWSOL_RANGE']
    if not (nowsol_min <= nowsol <= nowsol_max):
        return None

    # 条件3: 交易金额范围
    amount_min, amount_max = BUY_CONDITIONS_CONFIG['TRADE_AMOUNT_RANGE']
    abs_amount = abs(tradeamount)
    if not (amount_min <= abs_amount <= amount_max):
        return None

    # 条件4: 时间差
    time_diff_mode = BUY_CONDITIONS_CONFIG['TIME_DIFF_CHECK_MODE']
    if start_index > 0:
        prev_rec = trade_data[start_index - 1]
        try:
            prev_tradetime = int(prev_rec.get('tradetime', 0))
            time_diff_from_last = tradetime - prev_tradetime
            if time_diff_mode == 'online':
                td_min, td_max = BUY_CONDITIONS_CONFIG['TIME_DIFF_FROM_LAST_TRADE_RANGE']
                if not (td_min <= time_diff_from_last <= td_max):
                    return None
        except (TypeError, ValueError):
            return None
    else:
        return None

    # 条件5: 前N笔交易总和
    min_amount = BUY_CONDITIONS_CONFIG['FILTERED_TRADES_MIN_AMOUNT']
    trades_count = BUY_CONDITIONS_CONFIG['FILTERED_TRADES_COUNT']
    sum_range = BUY_CONDITIONS_CONFIG['FILTERED_TRADES_SUM_RANGE']
    filtered_sum = get_filtered_trades_sum(trade_data, start_index, min_amount, trades_count)
    if filtered_sum is None:
        return None
    sum_min, sum_max = sum_range
    if not (sum_min <= filtered_sum <= sum_max):
        return None

    # 条件6: 交易类型
    trade_type = BUY_CONDITIONS_CONFIG['TRADE_TYPE']
    if trade_type == 'buy' and tradeamount <= 0:
        return None
    elif trade_type == 'sell' and tradeamount >= 0:
        return None

    # 条件7: 最大金额检查
    max_amount_mode = BUY_CONDITIONS_CONFIG['MAX_AMOUNT_CHECK_MODE']
    if max_amount_mode == 'online':
        is_max = is_max_amount_in_recent_trades(trade_data, start_index, abs_amount,
                    BUY_CONDITIONS_CONFIG['MAX_AMOUNT_MIN_THRESHOLD'], BUY_CONDITIONS_CONFIG['MAX_AMOUNT_LOOKBACK_COUNT'])
        if not is_max:
            return None

    # 条件8: 波动率检查
    price_vol_mode = BUY_CONDITIONS_CONFIG['PRICE_VOLATILITY_CHECK_MODE']
    time_vol_mode = BUY_CONDITIONS_CONFIG['TIME_VOLATILITY_CHECK_MODE']
    amount_vol_mode = BUY_CONDITIONS_CONFIG['AMOUNT_VOLATILITY_CHECK_MODE']
    if price_vol_mode == 'online' or time_vol_mode == 'online' or amount_vol_mode == 'online':
        pv, tv, av = get_recent_trades_volatility(trade_data, start_index,
                        BUY_CONDITIONS_CONFIG['VOLATILITY_LOOKBACK_COUNT'], BUY_CONDITIONS_CONFIG['VOLATILITY_MIN_AMOUNT'], 'all')
        if price_vol_mode == 'online':
            pv_min, pv_max = BUY_CONDITIONS_CONFIG['PRICE_VOLATILITY_RANGE']
            if pv is None or not (pv_min <= pv <= pv_max):
                return None
        if time_vol_mode == 'online':
            tv_min, tv_max = BUY_CONDITIONS_CONFIG['TIME_VOLATILITY_RANGE']
            if tv is None or not (tv_min <= tv <= tv_max):
                return None
        if amount_vol_mode == 'online':
            av_min, av_max = BUY_CONDITIONS_CONFIG['AMOUNT_VOLATILITY_RANGE']
            if av is None or not (av_min <= av <= av_max):
                return None

    # 条件9: 价格比例
    if BUY_CONDITIONS_CONFIG['PRICE_RATIO_CHECK_MODE'] == 'online':
        try:
            current_price = float(rec.get('price', 0))
            if current_price > 0:
                price_ratio = get_price_ratio_to_min(trade_data, start_index, current_price, BUY_CONDITIONS_CONFIG['PRICE_RATIO_LOOKBACK_COUNT'])
                if price_ratio is not None:
                    r_min, r_max = BUY_CONDITIONS_CONFIG['PRICE_RATIO_RANGE']
                    if not (r_min <= price_ratio <= r_max):
                        return None
        except (TypeError, ValueError):
            pass

    # 条件10: 买单数量
    if BUY_CONDITIONS_CONFIG['BUY_COUNT_CHECK_MODE'] == 'online':
        bc, _ = get_buy_sell_count(trade_data, start_index, BUY_CONDITIONS_CONFIG['BUY_COUNT_LOOKBACK_COUNT'])
        if bc < BUY_CONDITIONS_CONFIG['BUY_COUNT_MIN']:
            return None

    # 条件11: 卖单数量
    if BUY_CONDITIONS_CONFIG['SELL_COUNT_CHECK_MODE'] == 'online':
        _, sc = get_buy_sell_count(trade_data, start_index, BUY_CONDITIONS_CONFIG['SELL_COUNT_LOOKBACK_COUNT'])
        if sc < BUY_CONDITIONS_CONFIG['SELL_COUNT_MIN']:
            return None

    # 条件12: 大单占比
    if BUY_CONDITIONS_CONFIG['LARGE_TRADE_RATIO_CHECK_MODE'] == 'online':
        lr, _ = get_large_small_trade_ratio(trade_data, start_index, BUY_CONDITIONS_CONFIG['LARGE_TRADE_RATIO_LOOKBACK'],
                    BUY_CONDITIONS_CONFIG['LARGE_TRADE_THRESHOLD'], BUY_CONDITIONS_CONFIG['SMALL_TRADE_THRESHOLD'])
        r_min, r_max = BUY_CONDITIONS_CONFIG['LARGE_TRADE_RATIO_RANGE']
        if not (r_min <= lr <= r_max):
            return None

    # 条件13: 小单占比
    if BUY_CONDITIONS_CONFIG['SMALL_TRADE_RATIO_CHECK_MODE'] == 'online':
        _, sr = get_large_small_trade_ratio(trade_data, start_index, BUY_CONDITIONS_CONFIG['SMALL_TRADE_RATIO_LOOKBACK'],
                    BUY_CONDITIONS_CONFIG['LARGE_TRADE_THRESHOLD'], BUY_CONDITIONS_CONFIG['SMALL_TRADE_THRESHOLD'])
        r_min, r_max = BUY_CONDITIONS_CONFIG['SMALL_TRADE_RATIO_RANGE']
        if not (r_min <= sr <= r_max):
            return None

    # 条件14: 连续买单
    if BUY_CONDITIONS_CONFIG['CONSECUTIVE_BUY_CHECK_MODE'] == 'online':
        cb, _ = get_consecutive_buy_sell_count(trade_data, start_index,
                    BUY_CONDITIONS_CONFIG['CONSECUTIVE_BUY_THRESHOLD'], BUY_CONDITIONS_CONFIG['CONSECUTIVE_SELL_THRESHOLD'])
        if cb < BUY_CONDITIONS_CONFIG['CONSECUTIVE_BUY_MIN']:
            return None

    # 条件15: 连续卖单
    if BUY_CONDITIONS_CONFIG['CONSECUTIVE_SELL_CHECK_MODE'] == 'online':
        _, cs = get_consecutive_buy_sell_count(trade_data, start_index,
                    BUY_CONDITIONS_CONFIG['CONSECUTIVE_BUY_THRESHOLD'], BUY_CONDITIONS_CONFIG['CONSECUTIVE_SELL_THRESHOLD'])
        if cs > BUY_CONDITIONS_CONFIG['CONSECUTIVE_SELL_MAX']:
            return None

    return start_index


# =============================================================================
# 卖出信号函数
# =============================================================================
def get_min_price_before_buy(trade_data, buy_index, lookback_count):
    prices = []
    start_idx = max(0, buy_index - lookback_count)
    for i in range(start_idx, buy_index):
        try:
            price = float(trade_data[i].get('price', 0))
            if price > 0:
                prices.append(price)
        except (TypeError, ValueError):
            continue
    return min(prices) if prices else None


def variant_find_sell_signal(trade_data, buy_index, buy_price, buy_time):
    original_buy_price = buy_price
    max_price = buy_price
    max_profit_rate = 0.0

    max_nowsol_sell = SELL_CONDITIONS_CONFIG['MAX_NOWSOL_SELL']
    loss_percentage = SELL_CONDITIONS_CONFIG['LOSS_PERCENTAGE']
    lookback_count = SELL_CONDITIONS_CONFIG['LOOKBACK_TRADES_FOR_MIN_PRICE']
    retracement_low = SELL_CONDITIONS_CONFIG['RETRACEMENT_LOW_PROFIT']
    retracement_high = SELL_CONDITIONS_CONFIG['RETRACEMENT_HIGH_PROFIT']
    high_profit_threshold = SELL_CONDITIONS_CONFIG['HIGH_PROFIT_THRESHOLD']
    max_hold_seconds = SELL_CONDITIONS_CONFIG['MAX_HOLD_TIME_SECONDS']
    quiet_period_enabled = SELL_CONDITIONS_CONFIG['QUIET_PERIOD_ENABLED']
    quiet_period_seconds = SELL_CONDITIONS_CONFIG['QUIET_PERIOD_SECONDS']
    quiet_period_min_amount = SELL_CONDITIONS_CONFIG['QUIET_PERIOD_MIN_AMOUNT']

    min_price_before_buy = get_min_price_before_buy(trade_data, buy_index, lookback_count)

    for i in range(buy_index, len(trade_data)):
        trade = trade_data[i]
        current_price = trade['price']
        current_time = trade['tradetime']
        current_nowsol = float(trade.get('nowsol', 0))
        current_tradeamount = float(trade.get('tradeamount', 0))

        if current_price > max_price:
            max_price = current_price
            max_profit_rate = (max_price - original_buy_price) / original_buy_price

        current_profit_rate = (current_price - original_buy_price) / original_buy_price

        if current_nowsol >= max_nowsol_sell:
            return i, "市值止盈"

        if current_profit_rate <= -loss_percentage:
            if min_price_before_buy is not None and current_price < min_price_before_buy:
                return i, "亏损止损"

        if max_price > original_buy_price:
            retracement = (max_price - current_price) / max_price
            if max_profit_rate < high_profit_threshold:
                if retracement >= retracement_low:
                    return i, "回撤止损(低)"
            else:
                if retracement >= retracement_high:
                    return i, "回撤止损(高)"

        hold_time_seconds = (current_time - buy_time) / 1000
        if hold_time_seconds > max_hold_seconds:
            return (i - 1 if i > buy_index else i), "时间止损"

        if quiet_period_enabled and current_tradeamount < 0:
            quiet_period_start_time = current_time - quiet_period_seconds * 1000
            has_large_trade = False
            for j in range(i - 1, buy_index - 1, -1):
                prev_trade = trade_data[j]
                prev_time = prev_trade['tradetime']
                if prev_time < quiet_period_start_time:
                    break
                prev_amount = abs(float(prev_trade.get('tradeamount', 0)))
                if prev_amount >= quiet_period_min_amount:
                    has_large_trade = True
                    break
            if not has_large_trade:
                return i, "冷淡期卖出"

    return len(trade_data) - 1, "强制卖出"


# =============================================================================
# Monkey patch - 确保替换生效
# =============================================================================
# 直接替换module级别的函数引用
pump.find_buy_signal = variant_find_buy_signal
pump.find_sell_signal = variant_find_sell_signal

# 如果pump.backtest_mint内部通过局部引用调用find_buy_signal，
# 还需要替换pump模块全局字典中的引用
import types
for name, obj in vars(pump).items():
    if callable(obj) and isinstance(obj, types.FunctionType):
        # 检查函数的全局命名空间中是否有find_buy_signal
        if 'find_buy_signal' in obj.__globals__:
            obj.__globals__['find_buy_signal'] = variant_find_buy_signal
        if 'find_sell_signal' in obj.__globals__:
            obj.__globals__['find_sell_signal'] = variant_find_sell_signal


# =============================================================================
# 回测结果收集器（含debug快照）
# =============================================================================
class BacktestResultCollector:
    """收集回测结果统计数据和debug快照"""

    DEBUG_CONDITIONS = [
        ('TIME_DIFF', 'TIME_DIFF_CHECK_MODE', 'TIME_DIFF_BUCKETS', 'TIME_DIFF_FROM_LAST_TRADE_RANGE'),
        ('MAX_AMOUNT', 'MAX_AMOUNT_CHECK_MODE', None, None),
        ('PRICE_VOLATILITY', 'PRICE_VOLATILITY_CHECK_MODE', 'PRICE_VOLATILITY_BUCKETS', 'PRICE_VOLATILITY_RANGE'),
        ('TIME_VOLATILITY', 'TIME_VOLATILITY_CHECK_MODE', 'TIME_VOLATILITY_BUCKETS', 'TIME_VOLATILITY_RANGE'),
        ('AMOUNT_VOLATILITY', 'AMOUNT_VOLATILITY_CHECK_MODE', 'AMOUNT_VOLATILITY_BUCKETS', 'AMOUNT_VOLATILITY_RANGE'),
        ('PRICE_RATIO', 'PRICE_RATIO_CHECK_MODE', 'PRICE_RATIO_BUCKETS', 'PRICE_RATIO_RANGE'),
        ('BUY_COUNT', 'BUY_COUNT_CHECK_MODE', 'BUY_COUNT_BUCKETS', None),
        ('SELL_COUNT', 'SELL_COUNT_CHECK_MODE', 'SELL_COUNT_BUCKETS', None),
        ('LARGE_TRADE_RATIO', 'LARGE_TRADE_RATIO_CHECK_MODE', 'LARGE_TRADE_RATIO_BUCKETS', 'LARGE_TRADE_RATIO_RANGE'),
        ('SMALL_TRADE_RATIO', 'SMALL_TRADE_RATIO_CHECK_MODE', 'SMALL_TRADE_RATIO_BUCKETS', 'SMALL_TRADE_RATIO_RANGE'),
        ('CONSECUTIVE_BUY', 'CONSECUTIVE_BUY_CHECK_MODE', 'CONSECUTIVE_BUY_BUCKETS', None),
        ('CONSECUTIVE_SELL', 'CONSECUTIVE_SELL_CHECK_MODE', 'CONSECUTIVE_SELL_BUCKETS', None),
    ]

    def __init__(self):
        self.reset()

    def reset(self):
        self.total_trades = 0
        self.profitable_trades = 0
        self.total_profit_sol = 0.0
        self.profit_rates = []
        self.trade_debug_records = []

    def collect_from_trades(self, trades):
        for trade in trades:
            self.total_trades += 1
            profit_rate = trade.get('profit_rate', 0.0)
            self.profit_rates.append(profit_rate)
            is_profitable = trade.get('is_profitable', False)
            if is_profitable:
                self.profitable_trades += 1

            # 计算盈利金额
            profit_sol = trade.get('profit_sol', None)
            if profit_sol is not None:
                self.total_profit_sol += profit_sol
            else:
                buy_amount = trade.get('buy_amount', None) or trade.get('tradeamount', None) or trade.get('amount', None)
                if buy_amount and float(buy_amount) > 0:
                    self.total_profit_sol += profit_rate * float(buy_amount)
                else:
                    amount_min, amount_max = BUY_CONDITIONS_CONFIG.get('TRADE_AMOUNT_RANGE', (0.3, 2.0))
                    approx_amount = (amount_min + amount_max) / 2
                    self.total_profit_sol += profit_rate * approx_amount

            # 收集debug快照数据
            debug_record = {'profit_rate': profit_rate, 'is_profitable': is_profitable}
            for field in ['time_diff', 'is_max_amount', 'price_volatility', 'time_volatility',
                          'amount_volatility', 'price_ratio', 'buy_count', 'sell_count',
                          'large_trade_ratio', 'small_trade_ratio', 'consecutive_buy', 'consecutive_sell']:
                if field in trade:
                    debug_record[field] = trade[field]
            self.trade_debug_records.append(debug_record)

    def get_summary(self):
        win_rate = self.profitable_trades / self.total_trades if self.total_trades > 0 else 0.0
        avg_profit_rate = sum(self.profit_rates) / len(self.profit_rates) if self.profit_rates else 0.0
        return {
            'total_trades': self.total_trades,
            'profitable_trades': self.profitable_trades,
            'win_rate': win_rate,
            'total_profit_sol': self.total_profit_sol,
            'avg_profit_rate': avg_profit_rate,
        }

    def get_debug_snapshot(self):
        """获取debug模式的分桶统计快照"""
        snapshot = {}
        config = BUY_CONDITIONS_CONFIG

        for cond_name, mode_key, buckets_key, range_key in self.DEBUG_CONDITIONS:
            if config.get(mode_key) != 'debug':
                continue
            if buckets_key is None:
                continue

            buckets = config.get(buckets_key, [])
            field_name = self._condition_to_field(cond_name)
            if not field_name:
                continue

            values_with_profit = []
            for rec in self.trade_debug_records:
                val = rec.get(field_name)
                if val is not None:
                    values_with_profit.append((val, rec['profit_rate'], rec['is_profitable']))

            if not values_with_profit:
                continue

            bucket_stats = self._compute_bucket_stats(values_with_profit, buckets)
            snapshot[cond_name] = {
                'mode_key': mode_key,
                'range_key': range_key,
                'buckets_key': buckets_key,
                'buckets': buckets,
                'field_name': field_name,
                'total_records': len(values_with_profit),
                'bucket_stats': bucket_stats,
            }
        return snapshot

    def _condition_to_field(self, cond_name):
        mapping = {
            'TIME_DIFF': 'time_diff', 'MAX_AMOUNT': 'is_max_amount',
            'PRICE_VOLATILITY': 'price_volatility', 'TIME_VOLATILITY': 'time_volatility',
            'AMOUNT_VOLATILITY': 'amount_volatility', 'PRICE_RATIO': 'price_ratio',
            'BUY_COUNT': 'buy_count', 'SELL_COUNT': 'sell_count',
            'LARGE_TRADE_RATIO': 'large_trade_ratio', 'SMALL_TRADE_RATIO': 'small_trade_ratio',
            'CONSECUTIVE_BUY': 'consecutive_buy', 'CONSECUTIVE_SELL': 'consecutive_sell',
        }
        return mapping.get(cond_name)

    def _compute_bucket_stats(self, values_with_profit, buckets):
        bucket_stats = []
        # Use 1e9 instead of float('inf') to ensure valid JSON output (Infinity is not valid JSON)
        INF_REPLACEMENT = 1e9
        for i in range(len(buckets)):
            low = buckets[i]
            high = buckets[i + 1] if i + 1 < len(buckets) else INF_REPLACEMENT
            bucket_name = f"[{low}, {high})" if high != INF_REPLACEMENT else f"[{low}, +∞)"

            in_bucket = [(v, pr, ip) for v, pr, ip in values_with_profit if low <= v < high]
            count = len(in_bucket)
            if count == 0:
                bucket_stats.append({'name': bucket_name, 'low': low, 'high': high,
                    'count': 0, 'profitable': 0, 'avg_profit_rate': 0.0, 'win_rate': 0.0})
                continue

            profitable_count = sum(1 for _, _, ip in in_bucket if ip)
            avg_pr = sum(pr for _, pr, _ in in_bucket) / count
            wr = profitable_count / count
            bucket_stats.append({'name': bucket_name, 'low': low, 'high': high,
                'count': count, 'profitable': profitable_count, 'avg_profit_rate': avg_pr, 'win_rate': wr})
        return bucket_stats


# =============================================================================
# 全局对象
# =============================================================================
result_collector = BacktestResultCollector()
original_backtest_mint = pump.backtest_mint


def wrapped_backtest_mint(mint_name, mint_data):
    """包装的回测函数，在每笔交易上通过 buy_trigger_index 重新计算debug指标"""
    trades = original_backtest_mint(mint_name, mint_data)
    
    trade_data = mint_data.get('trade_data', [])
    
    for trade in trades:
        buy_trigger_index = trade.get('buy_trigger_index', None)
        if buy_trigger_index is None:
            result_collector.collect_from_trades([trade])
            continue
        
        # 通过 buy_trigger_index 重新计算所有debug指标并注入到trade中
        try:
            rec = trade_data[buy_trigger_index]
            tradetime = int(rec.get('tradetime', 0))
            abs_amount = abs(float(rec.get('tradeamount', 0)))
        except (IndexError, TypeError, ValueError):
            result_collector.collect_from_trades([trade])
            continue
        
        # time_diff
        if buy_trigger_index > 0:
            try:
                prev_tradetime = int(trade_data[buy_trigger_index - 1].get('tradetime', 0))
                trade['time_diff'] = tradetime - prev_tradetime
            except (TypeError, ValueError):
                pass
        
        # 波动率 (price, time, amount)
        try:
            pv, tv, av = get_recent_trades_volatility(trade_data, buy_trigger_index,
                            BUY_CONDITIONS_CONFIG['VOLATILITY_LOOKBACK_COUNT'],
                            BUY_CONDITIONS_CONFIG['VOLATILITY_MIN_AMOUNT'], 'all')
            if pv is not None:
                trade['price_volatility'] = pv
            if tv is not None:
                trade['time_volatility'] = tv
            if av is not None:
                trade['amount_volatility'] = av
        except Exception:
            pass
        
        # is_max_amount
        try:
            is_max = is_max_amount_in_recent_trades(trade_data, buy_trigger_index, abs_amount,
                        BUY_CONDITIONS_CONFIG['MAX_AMOUNT_MIN_THRESHOLD'],
                        BUY_CONDITIONS_CONFIG['MAX_AMOUNT_LOOKBACK_COUNT'])
            trade['is_max_amount'] = 1.0 if is_max else 0.0
        except Exception:
            pass
        
        # price_ratio
        try:
            current_price = float(rec.get('price', 0))
            if current_price > 0:
                pr = get_price_ratio_to_min(trade_data, buy_trigger_index, current_price,
                        BUY_CONDITIONS_CONFIG['PRICE_RATIO_LOOKBACK_COUNT'])
                if pr is not None:
                    trade['price_ratio'] = pr
        except Exception:
            pass
        
        # buy_count, sell_count
        try:
            bc, sc = get_buy_sell_count(trade_data, buy_trigger_index,
                        BUY_CONDITIONS_CONFIG['BUY_COUNT_LOOKBACK_COUNT'])
            trade['buy_count'] = bc
            trade['sell_count'] = sc
        except Exception:
            pass
        
        # large_trade_ratio, small_trade_ratio
        try:
            lr, sr = get_large_small_trade_ratio(trade_data, buy_trigger_index,
                        BUY_CONDITIONS_CONFIG['LARGE_TRADE_RATIO_LOOKBACK'],
                        BUY_CONDITIONS_CONFIG['LARGE_TRADE_THRESHOLD'],
                        BUY_CONDITIONS_CONFIG['SMALL_TRADE_THRESHOLD'])
            trade['large_trade_ratio'] = lr
            trade['small_trade_ratio'] = sr
        except Exception:
            pass
        
        # consecutive_buy, consecutive_sell
        try:
            cb, cs_val = get_consecutive_buy_sell_count(trade_data, buy_trigger_index,
                        BUY_CONDITIONS_CONFIG['CONSECUTIVE_BUY_THRESHOLD'],
                        BUY_CONDITIONS_CONFIG['CONSECUTIVE_SELL_THRESHOLD'])
            trade['consecutive_buy'] = cb
            trade['consecutive_sell'] = cs_val
        except Exception:
            pass
        
        result_collector.collect_from_trades([trade])
    
    return trades


pump.backtest_mint = wrapped_backtest_mint


# =============================================================================
# 参数组合生成与辅助函数
# =============================================================================
def generate_param_combinations():
    keys = list(PARAM_SEARCH_SPACE.keys())
    values = list(PARAM_SEARCH_SPACE.values())
    combinations = list(itertools.product(*values))
    return [dict(zip(keys, combo)) for combo in combinations]


def build_config(params):
    config = copy.deepcopy(BASE_BUY_CONFIG)
    config.update(params)
    return config


def format_params(params):
    parts = []
    for key, value in params.items():
        short_key = key.replace('FILTERED_TRADES_', 'FT_').replace('TIME_FROM_CREATION_', 'TFC_')
        parts.append(f"{short_key}={value}")
    return ", ".join(parts)


def run_single_backtest(params, log_file, silent=True):
    """执行单次回测，返回结果和debug快照"""
    global BUY_CONDITIONS_CONFIG
    config = build_config(params)
    BUY_CONDITIONS_CONFIG = config
    result_collector.reset()

    if silent:
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            pump.run_backtest(log_file)
    else:
        pump.run_backtest(log_file)

    summary = result_collector.get_summary()
    debug_snapshot = result_collector.get_debug_snapshot()
    
    # 诊断: 检查debug数据是否注入成功
    total_with_debug = sum(1 for rec in result_collector.trade_debug_records if 'time_diff' in rec)
    if summary['total_trades'] > 0 and total_with_debug == 0:
        print(f"    ⚠️ 诊断: {summary['total_trades']}笔交易, 但0笔含debug数据 (注入可能失败)")
    
    return {'params': params, 'config': config, 'summary': summary, 'debug_snapshot': debug_snapshot}


def meets_full_criteria(summary):
    return (summary['profitable_trades'] >= FILTER_THRESHOLDS['MIN_PROFITABLE_TRADES'] and
            summary['total_profit_sol'] >= FILTER_THRESHOLDS['MIN_TOTAL_PROFIT_SOL'] and
            summary['win_rate'] >= FILTER_THRESHOLDS['MIN_WIN_RATE'] and
            summary['avg_profit_rate'] >= FILTER_THRESHOLDS['MIN_AVG_PROFIT_RATE'])


def print_result_line(idx, total, result, tag=""):
    s = result['summary']
    params_str = format_params(result['params'])
    status = f" {tag}" if tag else ""
    print(f"  [{idx}/{total}] {params_str}")
    print(f"    交易数: {s['total_trades']}, 盈利数: {s['profitable_trades']}, "
          f"胜率: {s['win_rate']*100:.2f}%, 总盈利: {s['total_profit_sol']:.2f}SOL, "
          f"平均盈利率: {s['avg_profit_rate']*100:.2f}%{status}")


def print_debug_snapshot(snapshot, indent="    "):
    if not snapshot:
        print(f"{indent}(无debug快照数据)")
        return
    for cond_name, data in snapshot.items():
        print(f"\n{indent}【{cond_name}】 总记录数: {data['total_records']}")
        for bs in data['bucket_stats']:
            if bs['count'] == 0:
                continue
            print(f"{indent}  {bs['name']}: {bs['count']}笔 | "
                  f"盈利: {bs['profitable']} ({bs['win_rate']*100:.1f}%) | "
                  f"平均盈利率: {bs['avg_profit_rate']*100:.2f}%")


def extract_profitable_range_from_snapshot(snapshot, condition_order):
    """
    从debug快照中按优先级顺序查找平均盈利率>0%的分桶，提取范围。
    返回 (条件名, mode_key, range_key, (min, max)) 或 None
    """
    for cond_name in condition_order:
        if cond_name not in snapshot:
            continue
        data = snapshot[cond_name]
        range_key = data.get('range_key')
        if not range_key:
            continue

        profitable_buckets = [bs for bs in data['bucket_stats'] if bs['count'] > 0 and bs['avg_profit_rate'] > 0.0]
        if not profitable_buckets:
            continue

        range_min = min(bs['low'] for bs in profitable_buckets)
        range_max = max(bs['high'] if bs['high'] != float('inf') else 999999 for bs in profitable_buckets)
        mode_key = data['mode_key']
        return cond_name, mode_key, range_key, (range_min, range_max)
    return None


def run_backtests_concurrent(param_list, log_file, max_workers=None):
    """Run run_single_backtest over param_list in parallel and return list of results."""
    if max_workers is None:
        max_workers = min(8, (multiprocessing.cpu_count() or 2) * 2)
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(run_single_backtest, p, log_file, True): p for p in param_list}
        for fut in concurrent.futures.as_completed(futures):
            try:
                res = fut.result()
            except Exception as e:
                res = {'params': futures[fut], 'config': None, 'summary': {'total_trades': 0, 'profitable_trades': 0, 'win_rate': 0.0, 'total_profit_sol': 0.0, 'avg_profit_rate': 0.0}, 'debug_snapshot': {}, 'error': str(e)}
            results.append(res)
    return results


# =============================================================================
# Step5 筛选阈值
# =============================================================================
STEP5_THRESHOLDS = {
    'MIN_PROFITABLE_TRADES': 300,   # 盈利单数>300
    'MIN_AVG_PROFIT_RATE': 0.005,   # 0.5%
    'MIN_WIN_RATE': 0.35,
}

# =============================================================================
# 主流程: Step2 → Step3 → Step4 → Step5
# =============================================================================
def main():
    log_file = '/Users/xcold/Desktop/js_log_mint_0209.log'

    print("=" * 80)
    print("多步骤参数优化回测")
    print("=" * 80)

    overall_start = time.time()

    # =====================================================================
    # STEP 2: 基础参数组合回测
    # =====================================================================
    print("\n" + "=" * 80)
    print("STEP 2: 基础参数组合回测")
    print("=" * 80)

    param_combinations = generate_param_combinations()
    total_combinations = len(param_combinations)
    print(f"\n总参数组合数: {total_combinations}")
    print(f"\n搜索空间:")
    for key, values in PARAM_SEARCH_SPACE.items():
        print(f"  {key}: {values}")

    step2_all_results = []
    step2_start = time.time()

    # STEP2a: run a single initial baseline using the first option of each search key
    initial_params = {}
    for k, v in PARAM_SEARCH_SPACE.items():
        initial_params[k] = v[0] if isinstance(v, (list, tuple)) and len(v) > 0 else v

    print("\n  → STEP2a: 先运行每个条件的第一个组合 (快速判断)")
    baseline_start = time.time()
    baseline_result = run_single_backtest(initial_params, log_file, silent=True)
    baseline_result['time'] = time.time() - baseline_start
    step2_all_results.append(baseline_result)
    print_result_line(1, total_combinations, baseline_result, "(baseline)")

    # If baseline already meets the strict FILTER_THRESHOLDS, we can continue to analysis
    if meets_full_criteria(baseline_result['summary']):
        print("  ✅ 基线组合已满足Step3要求，跳过其余组合回测")
        remaining_results = []
    else:
        # STEP2b: 并发执行其余参数组合以加速搜索
        print("\n  → STEP2b: 并发执行其余组合回测（加速）")
        remaining_params = []
        baseline_key = json.dumps(initial_params, sort_keys=True, default=str)
        for p in param_combinations:
            if json.dumps(p, sort_keys=True, default=str) == baseline_key:
                continue
            remaining_params.append(p)

        if remaining_params:
            concurrent_results = run_backtests_concurrent(remaining_params, log_file)
            # attach timing approximately
            for res in concurrent_results:
                res['time'] = time.time() - step2_start
                step2_all_results.append(res)
                idx = len(step2_all_results)
                s = res['summary']
                tag = "✅ 满足全部条件" if meets_full_criteria(s) else ""
                print_result_line(idx, total_combinations, res, tag)
        else:
            print("  (没有需要并发回测的组合)")

    step2_time = time.time() - step2_start
    print(f"\nStep2完成, 耗时: {step2_time:.1f}s")

    # =====================================================================
    # STEP 3: 判断是否已有满足条件的组合
    # =====================================================================
    print("\n" + "=" * 80)
    print("STEP 3: 判断是否已有满足全部条件的组合")
    print(f"  条件: 盈利数>{FILTER_THRESHOLDS['MIN_PROFITABLE_TRADES']}, "
          f"总盈利>{FILTER_THRESHOLDS['MIN_TOTAL_PROFIT_SOL']}SOL, "
          f"胜率>{FILTER_THRESHOLDS['MIN_WIN_RATE']*100:.0f}%, "
          f"平均盈利率>{FILTER_THRESHOLDS['MIN_AVG_PROFIT_RATE']*100:.1f}%")
    print("=" * 80)

    step3_qualified = [r for r in step2_all_results if meets_full_criteria(r['summary'])]

    if step3_qualified:
        step3_qualified.sort(key=lambda x: x['summary']['total_profit_sol'], reverse=True)
        print(f"\n  ✅ 找到 {len(step3_qualified)} 个满足全部条件的组合，跳过Step4，直接进入Step5")
        final_results = step3_qualified + step2_all_results
        final_step = "Step3(直接满足)"
    else:
        print(f"\n  ⚠️ 没有满足全部条件的组合 → 进入Step4")

        # =================================================================
        # STEP 4: 分析TIME_DIFF debug分桶 → 提取盈利桶 → 设为online再回测
        # =================================================================
        print("\n" + "=" * 80)
        print("STEP 4: 分析TIME_DIFF分桶数据 → 提取盈利范围 → 再回测")
        print("=" * 80)

        step4_results = []
        step4_total = 0

        for cand_idx, candidate in enumerate(step2_all_results):
            snapshot = candidate['debug_snapshot']
            base_params = candidate['params']
            s = candidate['summary']

            print(f"\n  {'─' * 60}")
            print(f"  组合 #{cand_idx+1}: {format_params(base_params)}")
            print(f"  基础结果: 交易:{s['total_trades']} 盈利:{s['profitable_trades']} "
                  f"胜率:{s['win_rate']*100:.2f}% 总盈利:{s['total_profit_sol']:.2f}SOL "
                  f"平均:{s['avg_profit_rate']*100:.2f}%")

            # 检查 TIME_DIFF 的 debug 数据
            if 'TIME_DIFF' not in snapshot:
                print(f"  ⚠️ 无TIME_DIFF debug数据，跳过")
                if snapshot:
                    print(f"    (snapshot包含: {list(snapshot.keys())})")
                else:
                    print(f"    (snapshot为空，debug指标可能未注入到交易记录中)")
                continue

            td_data = snapshot['TIME_DIFF']
            print(f"\n  TIME_DIFF 分桶数据:")
            for bs in td_data['bucket_stats']:
                if bs['count'] == 0:
                    continue
                print(f"    {bs['name']}: {bs['count']}笔 | "
                      f"盈利: {bs['profitable']} ({bs['win_rate']*100:.1f}%) | "
                      f"平均盈利率: {bs['avg_profit_rate']*100:.2f}%")

            # 找出平均盈利率 > -0.1% 的分桶
            profitable_buckets = [bs for bs in td_data['bucket_stats']
                                  if bs['count'] > 0 and bs['avg_profit_rate'] > -0.001]
            if not profitable_buckets:
                print(f"  ⚠️ 无平均盈利率>-0.1%的分桶，跳过")
                continue

            total_hits = sum(bs['count'] for bs in profitable_buckets)
            print(f"\n  盈利分桶: {len(profitable_buckets)} 个, 命中总数: {total_hits}")

            if total_hits < 300:
                print(f"  ⚠️ 命中总数 {total_hits} < 300，跳过")
                continue

            # 提取范围
            range_min = min(bs['low'] for bs in profitable_buckets)
            range_max = max(bs['high'] if bs['high'] != float('inf') else 999999 for bs in profitable_buckets)
            new_range = (range_min, range_max)
            print(f"  → 提取TIME_DIFF盈利范围: {new_range}")
            print(f"  → 设置 TIME_DIFF_CHECK_MODE='online', TIME_DIFF_FROM_LAST_TRADE_RANGE={new_range}")

            # 构建新参数
            new_params = copy.deepcopy(base_params)
            new_params['TIME_DIFF_CHECK_MODE'] = 'online'
            new_params['TIME_DIFF_FROM_LAST_TRADE_RANGE'] = new_range

            print(f"  → 开始回测...")
            step4_total += 1
            result = run_single_backtest(new_params, log_file, silent=True)
            result['time'] = time.time() - overall_start
            result['source_candidate'] = cand_idx
            result['optimized_condition'] = 'TIME_DIFF'
            result['optimized_range'] = new_range
            step4_results.append(result)

            rs = result['summary']
            tag = "✅ 满足全部条件" if meets_full_criteria(rs) else ""
            print_result_line(step4_total, len(step2_all_results), result, tag)

        print(f"\n  Step4完成, 共{step4_total}次回测")

        # 合并所有结果
        final_results = step4_results + step2_all_results
        final_step = "Step4"

    # =====================================================================
    # STEP 5: 筛选并打印最终结果
    # =====================================================================
    print("\n" + "=" * 80)
    print(f"STEP 5: 最终结果筛选与输出 (来源: {final_step})")
    print(f"  筛选条件: 盈利单数>{STEP5_THRESHOLDS['MIN_PROFITABLE_TRADES']}, "
          f"平均盈利率>{STEP5_THRESHOLDS['MIN_AVG_PROFIT_RATE']*100:.1f}%, "
          f"胜率>{STEP5_THRESHOLDS['MIN_WIN_RATE']*100:.0f}%")
    print("=" * 80)

    # 按step5条件筛选
    step5_qualified = []
    for r in final_results:
        s = r['summary']
        if (s['profitable_trades'] > STEP5_THRESHOLDS['MIN_PROFITABLE_TRADES'] and
            s['avg_profit_rate'] > STEP5_THRESHOLDS['MIN_AVG_PROFIT_RATE'] and
            s['win_rate'] > STEP5_THRESHOLDS['MIN_WIN_RATE']):
            step5_qualified.append(r)

    # 去重 (按params字符串去重)
    seen = set()
    unique_qualified = []
    for r in step5_qualified:
        key = json.dumps(r['params'], sort_keys=True, default=str)
        if key not in seen:
            seen.add(key)
            unique_qualified.append(r)
    step5_qualified = sorted(unique_qualified, key=lambda x: x['summary']['avg_profit_rate'], reverse=True)

    if not step5_qualified:
        print(f"\n  ⚠️ 没有满足Step5条件的组合，取所有结果中最优的")
        all_sorted = sorted(final_results, key=lambda x: x['summary']['avg_profit_rate'], reverse=True)
        seen2 = set()
        for r in all_sorted[:5]:
            key = json.dumps(r['params'], sort_keys=True, default=str)
            if key not in seen2:
                seen2.add(key)
                step5_qualified.append(r)
        print(f"  取平均盈利率最高的 {len(step5_qualified)} 个组合:")

    # 打印结果
    print(f"\n  满足条件的组合: {len(step5_qualified)} 个")
    print(f"\n  {'─' * 100}")
    print(f"  {'排名':<4} {'交易数':<8} {'盈利数':<8} {'胜率':<8} {'总盈利(SOL)':<14} {'平均盈利率':<12} {'参数'}")
    print(f"  {'─' * 100}")

    for rank, result in enumerate(step5_qualified, 1):
        s = result['summary']
        params_str = format_params(result['params'])
        opt = f" [优化:{result['optimized_condition']}]" if 'optimized_condition' in result else ""
        print(f"  #{rank:<3} {s['total_trades']:<8} {s['profitable_trades']:<8} "
              f"{s['win_rate']*100:<7.2f}% {s['total_profit_sol']:<13.2f} "
              f"{s['avg_profit_rate']*100:<11.2f}% {params_str}{opt}")

    # 详细输出每个满足条件的组合 + debug 盈利分桶
    for rank, result in enumerate(step5_qualified, 1):
        s = result['summary']
        p = result['params']
        print(f"\n{'=' * 80}")
        print(f"组合 #{rank} 详细信息")
        print(f"{'=' * 80}")
        print(f"  交易数: {s['total_trades']}")
        print(f"  盈利交易数: {s['profitable_trades']}")
        print(f"  胜率: {s['win_rate']*100:.2f}%")
        print(f"  总盈利: {s['total_profit_sol']:.2f} SOL")
        print(f"  平均盈利率: {s['avg_profit_rate']*100:.2f}%")

        if 'optimized_condition' in result:
            print(f"  优化条件: {result['optimized_condition']}")
            print(f"  优化范围: {result['optimized_range']}")

        print(f"\n  参数配置:")
        for key, value in p.items():
            print(f"    {key}: {value}")

        # 打印debug模式下 平均盈利率>0% 且命中数>50 的分桶
        snapshot = result.get('debug_snapshot', {})
        if snapshot:
            print(f"\n  {'─' * 70}")
            print(f"  debug模式下盈利分桶 (平均盈利率>0.0% 且 命中数>50):")
            print(f"  {'─' * 70}")
            found_any = False
            for cond_name, data in snapshot.items():
                good_buckets = [bs for bs in data['bucket_stats']
                                if bs['count'] > 50 and bs['avg_profit_rate'] > 0.0]
                if not good_buckets:
                    continue
                found_any = True
                print(f"\n    【{cond_name}】 总记录数: {data['total_records']}")
                for bs in good_buckets:
                    print(f"      {bs['name']}: {bs['count']}笔 | "
                          f"盈利: {bs['profitable']} ({bs['win_rate']*100:.1f}%) | "
                          f"平均盈利率: {bs['avg_profit_rate']*100:.2f}%")
            if not found_any:
                print(f"    (无满足条件的分桶)")

    # 保存规则到 rule.json: 收集debug模式下 avg_profit_rate>0 且 count>50 的分桶，并按 params 合并为 conditions 列表
    try:
        grouped = {}
        for result in step5_qualified:
            snapshot = result.get('debug_snapshot', {})
            params = result.get('params', {}) or {}
            key = json.dumps(params, sort_keys=True, default=str)
            if key not in grouped:
                grouped[key] = {'params': params, 'conditions': []}
            for cond_name, data in snapshot.items():
                good_buckets = [bs for bs in data.get('bucket_stats', []) if bs.get('count', 0) > 50 and bs.get('avg_profit_rate', 0.0) > 0.0]
                if not good_buckets:
                    continue
                grouped[key]['conditions'].append({'condition': cond_name, 'buckets': good_buckets})

        merged_rules = list(grouped.values())
        if merged_rules:
            rule_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'rule.json'))
            # backup existing file
            try:
                if os.path.exists(rule_path):
                    bak_path = rule_path + '.bak'
                    shutil.copyfile(rule_path, bak_path)
            except Exception:
                pass
            with open(rule_path, 'w', encoding='utf-8') as rf:
                json.dump(merged_rules, rf, ensure_ascii=False, indent=2)
            total_conditions = sum(len(g['conditions']) for g in merged_rules)
            print(f"\n已将{total_conditions}个条件保存到: {rule_path}")
    except Exception as e:
        print(f"保存rule.json失败: {e}")

    # 输出最佳配置
    if step5_qualified:
        best = step5_qualified[0]
        print(f"\n{'=' * 80}")
        print(f"最佳配置 (可直接复制到 BUY_CONDITIONS_CONFIG):")
        print(f"{'=' * 80}")
        best_config = build_config(best['params'])
        print("BUY_CONDITIONS_CONFIG = {")
        for key, value in best_config.items():
            if isinstance(value, str):
                print(f"    '{key}': '{value}',")
            else:
                print(f"    '{key}': {value},")
        print("}")

    overall_time = time.time() - overall_start
    print(f"\n{'=' * 80}")
    print(f"优化完成! 总耗时: {overall_time:.1f}s")
    print(f"{'=' * 80}")


if __name__ == '__main__':
    main()
