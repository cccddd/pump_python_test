import sys, os, time
import itertools
import copy
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pump
import json
from typing import Dict, List, Optional, Tuple

STRATEGY_CONFIG = pump.STRATEGY_CONFIG

# =============================================================================
# 参数搜索空间定义
# =============================================================================
PARAM_SEARCH_SPACE = {
    'TIME_FROM_CREATION_MINUTES': [2, 3, 4, 5],
    'NOWSOL_RANGE': [(5, 15), (5, 30), (15, 30)],
    'FILTERED_TRADES_MIN_AMOUNT': [0.05, 0.1],
    'FILTERED_TRADES_COUNT': [7, 10],
    'FILTERED_TRADES_SUM_RANGE': [(-6.0, -1.0), (-6.0, -3.0), (-3.0, -1.0)],
}

# =============================================================================
# 筛选阈值
# =============================================================================
FILTER_THRESHOLDS = {
    'MIN_TOTAL_TRADES': 1000,       # 最小总交易数
    'MIN_TOTAL_PROFIT_SOL': 10.0,   # 最小总盈利(SOL)
    'MIN_WIN_RATE': 0.35,           # 最小胜率 35%
    'MIN_AVG_PROFIT_RATE': 0.01,    # 最小平均盈利率 1%
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
# 导入 rule_demo 中的辅助函数（直接复制关键函数避免循环依赖）
# =============================================================================

# 当前活跃的 BUY_CONDITIONS_CONFIG（会在每次回测前被更新）
BUY_CONDITIONS_CONFIG = {}


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

    # 条件1
    time_diff_seconds = (tradetime - creation_time) / 1000
    time_diff_minutes = time_diff_seconds / 60
    if time_diff_minutes < BUY_CONDITIONS_CONFIG['TIME_FROM_CREATION_MINUTES']:
        return None

    # 条件2
    nowsol_min, nowsol_max = BUY_CONDITIONS_CONFIG['NOWSOL_RANGE']
    if not (nowsol_min <= nowsol <= nowsol_max):
        return None

    # 条件3
    amount_min, amount_max = BUY_CONDITIONS_CONFIG['TRADE_AMOUNT_RANGE']
    abs_amount = abs(tradeamount)
    if not (amount_min <= abs_amount <= amount_max):
        return None

    # 条件4
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

    # 条件5
    min_amount = BUY_CONDITIONS_CONFIG['FILTERED_TRADES_MIN_AMOUNT']
    trades_count = BUY_CONDITIONS_CONFIG['FILTERED_TRADES_COUNT']
    sum_range = BUY_CONDITIONS_CONFIG['FILTERED_TRADES_SUM_RANGE']
    filtered_sum = get_filtered_trades_sum(trade_data, start_index, min_amount, trades_count)
    if filtered_sum is None:
        return None
    sum_min, sum_max = sum_range
    if not (sum_min <= filtered_sum <= sum_max):
        return None

    # 条件6
    trade_type = BUY_CONDITIONS_CONFIG['TRADE_TYPE']
    if trade_type == 'buy':
        if tradeamount <= 0:
            return None
    elif trade_type == 'sell':
        if tradeamount >= 0:
            return None

    # 条件7
    max_amount_mode = BUY_CONDITIONS_CONFIG['MAX_AMOUNT_CHECK_MODE']
    if max_amount_mode == 'online':
        max_amount_threshold = BUY_CONDITIONS_CONFIG['MAX_AMOUNT_MIN_THRESHOLD']
        max_amount_lookback = BUY_CONDITIONS_CONFIG['MAX_AMOUNT_LOOKBACK_COUNT']
        is_max = is_max_amount_in_recent_trades(trade_data, start_index, abs_amount, max_amount_threshold, max_amount_lookback)
        if not is_max:
            return None

    # 条件8
    price_volatility_mode = BUY_CONDITIONS_CONFIG['PRICE_VOLATILITY_CHECK_MODE']
    time_volatility_mode = BUY_CONDITIONS_CONFIG['TIME_VOLATILITY_CHECK_MODE']
    amount_volatility_mode = BUY_CONDITIONS_CONFIG['AMOUNT_VOLATILITY_CHECK_MODE']
    need_price = price_volatility_mode == 'online'
    need_time = time_volatility_mode == 'online'
    need_amount = amount_volatility_mode == 'online'
    if need_price or need_time or need_amount:
        volatility_lookback = BUY_CONDITIONS_CONFIG['VOLATILITY_LOOKBACK_COUNT']
        volatility_min_amount = BUY_CONDITIONS_CONFIG['VOLATILITY_MIN_AMOUNT']
        pv, tv, av = get_recent_trades_volatility(trade_data, start_index, volatility_lookback, volatility_min_amount, 'all')
        if price_volatility_mode == 'online':
            pv_min, pv_max = BUY_CONDITIONS_CONFIG['PRICE_VOLATILITY_RANGE']
            if pv is None or not (pv_min <= pv <= pv_max):
                return None
        if time_volatility_mode == 'online':
            tv_min, tv_max = BUY_CONDITIONS_CONFIG['TIME_VOLATILITY_RANGE']
            if tv is None or not (tv_min <= tv <= tv_max):
                return None
        if amount_volatility_mode == 'online':
            av_min, av_max = BUY_CONDITIONS_CONFIG['AMOUNT_VOLATILITY_RANGE']
            if av is None or not (av_min <= av <= av_max):
                return None

    # 条件9
    price_ratio_mode = BUY_CONDITIONS_CONFIG['PRICE_RATIO_CHECK_MODE']
    if price_ratio_mode == 'online':
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

    # 条件10
    buy_count_mode = BUY_CONDITIONS_CONFIG['BUY_COUNT_CHECK_MODE']
    if buy_count_mode == 'online':
        bc, _ = get_buy_sell_count(trade_data, start_index, BUY_CONDITIONS_CONFIG['BUY_COUNT_LOOKBACK_COUNT'])
        if bc < BUY_CONDITIONS_CONFIG['BUY_COUNT_MIN']:
            return None

    # 条件11
    sell_count_mode = BUY_CONDITIONS_CONFIG['SELL_COUNT_CHECK_MODE']
    if sell_count_mode == 'online':
        _, sc = get_buy_sell_count(trade_data, start_index, BUY_CONDITIONS_CONFIG['SELL_COUNT_LOOKBACK_COUNT'])
        if sc < BUY_CONDITIONS_CONFIG['SELL_COUNT_MIN']:
            return None

    # 条件12
    large_ratio_mode = BUY_CONDITIONS_CONFIG['LARGE_TRADE_RATIO_CHECK_MODE']
    if large_ratio_mode == 'online':
        lr, _ = get_large_small_trade_ratio(trade_data, start_index, BUY_CONDITIONS_CONFIG['LARGE_TRADE_RATIO_LOOKBACK'], BUY_CONDITIONS_CONFIG['LARGE_TRADE_THRESHOLD'], BUY_CONDITIONS_CONFIG['SMALL_TRADE_THRESHOLD'])
        r_min, r_max = BUY_CONDITIONS_CONFIG['LARGE_TRADE_RATIO_RANGE']
        if not (r_min <= lr <= r_max):
            return None

    # 条件13
    small_ratio_mode = BUY_CONDITIONS_CONFIG['SMALL_TRADE_RATIO_CHECK_MODE']
    if small_ratio_mode == 'online':
        _, sr = get_large_small_trade_ratio(trade_data, start_index, BUY_CONDITIONS_CONFIG['SMALL_TRADE_RATIO_LOOKBACK'], BUY_CONDITIONS_CONFIG['LARGE_TRADE_THRESHOLD'], BUY_CONDITIONS_CONFIG['SMALL_TRADE_THRESHOLD'])
        r_min, r_max = BUY_CONDITIONS_CONFIG['SMALL_TRADE_RATIO_RANGE']
        if not (r_min <= sr <= r_max):
            return None

    # 条件14
    consecutive_buy_mode = BUY_CONDITIONS_CONFIG['CONSECUTIVE_BUY_CHECK_MODE']
    if consecutive_buy_mode == 'online':
        cb, _ = get_consecutive_buy_sell_count(trade_data, start_index, BUY_CONDITIONS_CONFIG['CONSECUTIVE_BUY_THRESHOLD'], BUY_CONDITIONS_CONFIG['CONSECUTIVE_SELL_THRESHOLD'])
        if cb < BUY_CONDITIONS_CONFIG['CONSECUTIVE_BUY_MIN']:
            return None

    # 条件15
    consecutive_sell_mode = BUY_CONDITIONS_CONFIG['CONSECUTIVE_SELL_CHECK_MODE']
    if consecutive_sell_mode == 'online':
        _, cs = get_consecutive_buy_sell_count(trade_data, start_index, BUY_CONDITIONS_CONFIG['CONSECUTIVE_BUY_THRESHOLD'], BUY_CONDITIONS_CONFIG['CONSECUTIVE_SELL_THRESHOLD'])
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
            return i, f"市值止盈"

        if current_profit_rate <= -loss_percentage:
            if min_price_before_buy is not None and current_price < min_price_before_buy:
                return i, f"亏损止损"

        if max_price > original_buy_price:
            retracement = (max_price - current_price) / max_price
            if max_profit_rate < high_profit_threshold:
                if retracement >= retracement_low:
                    return i, f"回撤止损(低)"
            else:
                if retracement >= retracement_high:
                    return i, f"回撤止损(高)"

        hold_time_seconds = (current_time - buy_time) / 1000
        if hold_time_seconds > max_hold_seconds:
            if i > buy_index:
                return i - 1, f"时间止损"
            else:
                return i, f"时间止损"

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
                return i, f"冷淡期卖出"

    return len(trade_data) - 1, "强制卖出"


# =============================================================================
# Monkey patch
# =============================================================================
pump.find_buy_signal = variant_find_buy_signal
pump.find_sell_signal = variant_find_sell_signal


# =============================================================================
# 回测结果收集器
# =============================================================================
class BacktestResultCollector:
    """收集回测结果统计数据"""

    def __init__(self):
        self.reset()

    def reset(self):
        self.total_trades = 0
        self.profitable_trades = 0
        self.total_profit_sol = 0.0
        self.profit_rates = []

    def collect_from_trades(self, trades: List[Dict]):
        for trade in trades:
            self.total_trades += 1
            profit_rate = trade.get('profit_rate', 0.0)
            self.profit_rates.append(profit_rate)
            if trade.get('is_profitable', False):
                self.profitable_trades += 1
            # 计算盈利金额: 优先使用 profit_sol，其次用 sell_price - buy_price 的比例 * tradeamount
            profit_sol = trade.get('profit_sol', None)
            if profit_sol is not None:
                self.total_profit_sol += profit_sol
            else:
                # 用买入金额 * 盈利率来近似
                buy_price = trade.get('buy_price', 0)
                sell_price = trade.get('sell_price', 0)
                buy_amount = trade.get('buy_amount', None) or trade.get('tradeamount', None) or trade.get('amount', None)
                if buy_amount and buy_amount > 0:
                    self.total_profit_sol += profit_rate * buy_amount
                else:
                    # 使用 TRADE_AMOUNT_RANGE 的中间值作为近似买入金额
                    amount_min, amount_max = BUY_CONDITIONS_CONFIG.get('TRADE_AMOUNT_RANGE', (0.3, 2.0))
                    approx_amount = (amount_min + amount_max) / 2
                    self.total_profit_sol += profit_rate * approx_amount

    def get_summary(self) -> Dict:
        win_rate = self.profitable_trades / self.total_trades if self.total_trades > 0 else 0.0
        avg_profit_rate = sum(self.profit_rates) / len(self.profit_rates) if self.profit_rates else 0.0
        return {
            'total_trades': self.total_trades,
            'profitable_trades': self.profitable_trades,
            'win_rate': win_rate,
            'total_profit_sol': self.total_profit_sol,
            'avg_profit_rate': avg_profit_rate,
        }


# 全局结果收集器
result_collector = BacktestResultCollector()

# 保存原始的 backtest_mint 函数
original_backtest_mint = pump.backtest_mint


def wrapped_backtest_mint(mint_name: str, mint_data: Dict) -> List[Dict]:
    """包装的回测函数，用于收集回测结果"""
    trades = original_backtest_mint(mint_name, mint_data)
    result_collector.collect_from_trades(trades)
    return trades


# 替换 backtest_mint 函数
pump.backtest_mint = wrapped_backtest_mint


# =============================================================================
# 生成参数组合
# =============================================================================
def generate_param_combinations():
    """生成所有参数组合"""
    keys = list(PARAM_SEARCH_SPACE.keys())
    values = list(PARAM_SEARCH_SPACE.values())
    combinations = list(itertools.product(*values))

    param_list = []
    for combo in combinations:
        param_dict = dict(zip(keys, combo))
        param_list.append(param_dict)

    return param_list


def build_config(params: Dict) -> Dict:
    """根据参数组合构建完整的 BUY_CONDITIONS_CONFIG"""
    config = copy.deepcopy(BASE_BUY_CONFIG)
    config.update(params)
    return config


def format_params(params: Dict) -> str:
    """格式化参数为可读字符串"""
    parts = []
    for key, value in params.items():
        short_key = key.replace('FILTERED_TRADES_', 'FT_').replace('TIME_FROM_CREATION_', 'TFC_')
        parts.append(f"{short_key}={value}")
    return ", ".join(parts)


# =============================================================================
# 主流程
# =============================================================================
def main():
    log_file = '/Users/xcold/Desktop/js_log_mint_0209.log'

    # 预加载数据（只解析一次）
    print("=" * 80)
    print("参数优化回测")
    print("=" * 80)

    # 生成参数组合
    param_combinations = generate_param_combinations()
    total_combinations = len(param_combinations)
    print(f"\n总参数组合数: {total_combinations}")
    print(f"\n搜索空间:")
    for key, values in PARAM_SEARCH_SPACE.items():
        print(f"  {key}: {values}")
    print(f"\n筛选阈值:")
    for key, value in FILTER_THRESHOLDS.items():
        print(f"  {key}: {value}")
    print(f"\n{'=' * 80}")

    # 存储所有回测结果
    all_results = []
    qualified_results = []  # 满足筛选条件的结果

    start_time = time.time()

    for idx, params in enumerate(param_combinations):
        combo_start = time.time()

        # 构建配置
        config = build_config(params)

        # 更新全局 BUY_CONDITIONS_CONFIG
        global BUY_CONDITIONS_CONFIG
        BUY_CONDITIONS_CONFIG = config

        # 重置结果收集器
        result_collector.reset()

        # 执行回测（静默模式，抑制输出）
        import io
        import contextlib
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            pump.run_backtest(log_file)

        # 获取结果
        summary = result_collector.get_summary()
        combo_time = time.time() - combo_start

        # 构建结果记录
        result = {
            'index': idx + 1,
            'params': params,
            'summary': summary,
            'time': combo_time,
        }
        all_results.append(result)

        # 打印进度
        total_trades = summary['total_trades']
        win_rate = summary['win_rate']
        total_profit = summary['total_profit_sol']
        avg_rate = summary['avg_profit_rate']

        status = ""
        meets_criteria = (
            total_trades >= FILTER_THRESHOLDS['MIN_TOTAL_TRADES'] and
            total_profit >= FILTER_THRESHOLDS['MIN_TOTAL_PROFIT_SOL'] and
            win_rate >= FILTER_THRESHOLDS['MIN_WIN_RATE'] and
            avg_rate >= FILTER_THRESHOLDS['MIN_AVG_PROFIT_RATE']
        )

        if meets_criteria:
            status = " ✅ 满足条件"
            qualified_results.append(result)

        print(f"[{idx+1}/{total_combinations}] {format_params(params)}")
        print(f"  交易数: {total_trades}, 胜率: {win_rate*100:.2f}%, 总盈利: {total_profit:.2f}SOL, 平均盈利率: {avg_rate*100:.2f}%, 耗时: {combo_time:.1f}s{status}")

    total_time = time.time() - start_time

    # =============================================================================
    # 输出最终结果
    # =============================================================================
    print("\n" + "=" * 80)
    print("回测结果汇总")
    print("=" * 80)
    print(f"\n总参数组合: {total_combinations}")
    print(f"总耗时: {total_time:.1f}s")
    print(f"平均每组: {total_time/total_combinations:.1f}s")

    # 筛选总交易数 > 1000 的结果
    filtered_results = [r for r in all_results if r['summary']['total_trades'] >= FILTER_THRESHOLDS['MIN_TOTAL_TRADES']]

    print(f"\n总交易数 >= {FILTER_THRESHOLDS['MIN_TOTAL_TRADES']} 的组合: {len(filtered_results)}")

    if filtered_results:
        # 按总盈利金额排序
        filtered_results.sort(key=lambda x: x['summary']['total_profit_sol'], reverse=True)

        print(f"\n{'─' * 80}")
        print(f"按总盈利金额排序 (交易数 >= {FILTER_THRESHOLDS['MIN_TOTAL_TRADES']})")
        print(f"{'─' * 80}")
        print(f"{'排名':<4} {'交易数':<8} {'胜率':<8} {'总盈利(SOL)':<14} {'平均盈利率':<12} {'参数'}")
        print(f"{'─' * 80}")

        for rank, result in enumerate(filtered_results, 1):
            s = result['summary']
            params_str = format_params(result['params'])
            meets = "✅" if result in qualified_results else "  "
            print(f"{meets}{rank:<3} {s['total_trades']:<8} {s['win_rate']*100:<7.2f}% {s['total_profit_sol']:<13.2f} {s['avg_profit_rate']*100:<11.2f}% {params_str}")

        # 输出满足所有筛选条件的结果
        if qualified_results:
            qualified_results.sort(key=lambda x: x['summary']['total_profit_sol'], reverse=True)
            print(f"\n{'─' * 80}")
            print(f"满足所有筛选条件的组合 ({len(qualified_results)} 个)")
            print(f"  交易数 >= {FILTER_THRESHOLDS['MIN_TOTAL_TRADES']}")
            print(f"  总盈利 >= {FILTER_THRESHOLDS['MIN_TOTAL_PROFIT_SOL']} SOL")
            print(f"  胜率 >= {FILTER_THRESHOLDS['MIN_WIN_RATE']*100:.0f}%")
            print(f"  平均盈利率 >= {FILTER_THRESHOLDS['MIN_AVG_PROFIT_RATE']*100:.0f}%")
            print(f"{'─' * 80}")
            print(f"{'排名':<4} {'交易数':<8} {'胜率':<8} {'总盈利(SOL)':<14} {'平均盈利率':<12} {'参数'}")
            print(f"{'─' * 80}")

            for rank, result in enumerate(qualified_results, 1):
                s = result['summary']
                params_str = format_params(result['params'])
                print(f"  {rank:<3} {s['total_trades']:<8} {s['win_rate']*100:<7.2f}% {s['total_profit_sol']:<13.2f} {s['avg_profit_rate']*100:<11.2f}% {params_str}")
        else:
            print(f"\n⚠️  没有组合满足所有筛选条件")

        # 输出 TOP 10 最佳组合的详细配置
        print(f"\n{'=' * 80}")
        print(f"TOP 10 最佳参数组合详细配置")
        print(f"{'=' * 80}")

        for rank, result in enumerate(filtered_results[:10], 1):
            s = result['summary']
            p = result['params']
            print(f"\n{'─' * 40}")
            print(f"排名 #{rank}")
            print(f"{'─' * 40}")
            print(f"  交易数: {s['total_trades']}")
            print(f"  盈利交易数: {s['profitable_trades']}")
            print(f"  胜率: {s['win_rate']*100:.2f}%")
            print(f"  总盈利: {s['total_profit_sol']:.2f} SOL")
            print(f"  平均盈利率: {s['avg_profit_rate']*100:.2f}%")
            print(f"  参数配置:")
            for key, value in p.items():
                print(f"    {key}: {value}")
    else:
        print(f"\n⚠️  没有交易数 >= {FILTER_THRESHOLDS['MIN_TOTAL_TRADES']} 的组合")

    print(f"\n{'=' * 80}")
    print(f"优化完成! 总耗时: {total_time:.1f}s")
    print(f"{'=' * 80}")


if __name__ == '__main__':
    main()
