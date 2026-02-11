import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pump
import json
from typing import Dict, List, Optional, Tuple

STRATEGY_CONFIG = pump.STRATEGY_CONFIG

# =============================================================================
# 基本条件配置
# =============================================================================
BUY_CONDITIONS_CONFIG = {
    # 条件1: 距离创币时间（分钟）
    'TIME_FROM_CREATION_MINUTES': 3,  # 距离创币时间 >= 5 分钟
    # 条件2: 当前市值范围（nowsol字段）
    'NOWSOL_RANGE': (3, 35),  # nowsol 在 [5, 35] 范围内

    # 条件3: 当前交易单金额范围
    'TRADE_AMOUNT_RANGE': (0.3, 1.5),  # 交易金额绝对值在 [0.5, 2.0] 范围内
    
    # 条件4: 当前交易单距离上一个交易单的时间差（毫秒）
    # 'off' - 禁用此条件
    # 'online' - 启用此条件，进行实际过滤
    # 'debug' - 调试模式，只收集统计数据，不过滤
    'TIME_DIFF_CHECK_MODE': 'debug',  # 可选值: 'off', 'online', 'debug'
    'TIME_DIFF_FROM_LAST_TRADE_RANGE': (2000, 50000),  # 时间差在 [2000, 10000] 毫秒范围内 - online模式使用
    'TIME_DIFF_BUCKETS': [0, 500, 1000, 2000, 3000, 5000, 10000, 20000, 50000],  # 时间差分桶边界（毫秒）

    # 条件5: 过滤后的前N笔交易总和范围
    'FILTERED_TRADES_MIN_AMOUNT': 0.05,  # 过滤掉交易金额绝对值小于此值的交易
    'FILTERED_TRADES_COUNT': 7,  # 取前N笔有效交易
    'FILTERED_TRADES_SUM_RANGE': (1.0, 5.0),  # 交易金额总和范围
    
    # 条件6: 当前交易类型
    # 'buy' - 只匹配买入交易 (tradeamount > 0)
    # 'sell' - 只匹配卖出交易 (tradeamount < 0)
    # 'both' - 匹配买入和卖出交易
    'TRADE_TYPE': 'buy',  # 可选值: 'buy', 'sell', 'both'
    
    # 条件7: 当前交易金额是否为近T单中最大
    # 'off' - 禁用此条件
    # 'online' - 启用此条件，进行实际过滤
    # 'debug' - 调试模式，只收集统计数据，不过滤
    'MAX_AMOUNT_CHECK_MODE': 'debug',  # 可选值: 'off', 'online', 'debug'
    'MAX_AMOUNT_MIN_THRESHOLD': 0.05,  # 过滤掉交易金额绝对值小于此值的交易
    'MAX_AMOUNT_LOOKBACK_COUNT': 15,  # 向前查看的交易数量
    
    # 条件8: 近N个交易单的波动率检查
    'VOLATILITY_LOOKBACK_COUNT': 15,  # 向前查看的交易数量
    'VOLATILITY_MIN_AMOUNT': 0.1,  # 过滤掉交易金额绝对值小于此值的交易
    
    # 条件8a: 价格波动率
    # 'off' - 禁用此条件
    # 'online' - 启用此条件，进行实际过滤
    # 'debug' - 调试模式，只收集统计数据，不过滤
    'PRICE_VOLATILITY_CHECK_MODE': 'debug',  # 可选值: 'off', 'online', 'debug'
    'PRICE_VOLATILITY_RANGE': (0.0, 1.0),  # 价格波动率范围（标准差/均值）- online模式使用
    'PRICE_VOLATILITY_BUCKETS': [0.0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0],  # 价格波动率分桶边界
    
    # 条件8b: 时间波动率
    # 'off' - 禁用此条件
    # 'online' - 启用此条件，进行实际过滤
    # 'debug' - 调试模式，只收集统计数据，不过滤
    'TIME_VOLATILITY_CHECK_MODE': 'debug',  # 可选值: 'off', 'online', 'debug'
    'TIME_VOLATILITY_RANGE': (0.7, 5.0),  # 时间波动率范围（标准差/均值）- online模式使用
    'TIME_VOLATILITY_BUCKETS': [0.0, 0.1, 0.2, 0.5, 0.7, 1.0, 1.5, 2.0, 5.0, 10.0],  # 时间波动率分桶边界
    
    # 条件8c: 金额波动率
    # 'off' - 禁用此条件
    # 'online' - 启用此条件，进行实际过滤
    # 'debug' - 调试模式，只收集统计数据，不过滤
    'AMOUNT_VOLATILITY_CHECK_MODE': 'debug',  # 可选值: 'off', 'online', 'debug'
    'AMOUNT_VOLATILITY_RANGE': (0.2, 1.0),  # 金额波动率范围（标准差/均值）- online模式使用
    'AMOUNT_VOLATILITY_BUCKETS': [0.0, 0.2, 0.5, 0.7, 1.0, 1.5, 2.0, 3.0, 5.0],  # 金额波动率分桶边界
    
    # 条件9: 当前交易价格/近N单最低价的比例
    # 'off' - 禁用此条件
    # 'online' - 启用此条件，进行实际过滤
    # 'debug' - 调试模式，只收集统计数据，不过滤
    'PRICE_RATIO_CHECK_MODE': 'debug',  # 可选值: 'off', 'online', 'debug'
    'PRICE_RATIO_LOOKBACK_COUNT': 10,  # 向前查看的交易数量
    'PRICE_RATIO_RANGE': (0.0, 3.0),  # 价格比例范围 (当前价格/最低价 - 1) * 100，即涨幅百分比 - online模式使用
    'PRICE_RATIO_BUCKETS': [0.0, 1.0, 2.0, 3.0, 5.0, 10.0, 20.0, 50.0],  # 价格比例分桶边界（百分比）
    
    # 条件10: 近T个交易单里买单数量
    # 'off' - 禁用此条件
    # 'online' - 启用此条件，进行实际过滤
    # 'debug' - 调试模式，只收集统计数据，不过滤
    'BUY_COUNT_CHECK_MODE': 'debug',  # 可选值: 'off', 'online', 'debug'
    'BUY_COUNT_LOOKBACK_COUNT': 15,  # 向前查看的交易数量
    'BUY_COUNT_MIN': 5,  # 最少买单数量 - online模式使用
    'BUY_COUNT_BUCKETS': [0, 2, 4, 6, 8, 10, 12, 15],  # 买单数量分桶边界
    
    # 条件11: 近T个交易单里卖单数量
    # 'off' - 禁用此条件
    # 'online' - 启用此条件，进行实际过滤
    # 'debug' - 调试模式，只收集统计数据，不过滤
    'SELL_COUNT_CHECK_MODE': 'debug',  # 可选值: 'off', 'online', 'debug'
    'SELL_COUNT_LOOKBACK_COUNT': 15,  # 向前查看的交易数量
    'SELL_COUNT_MIN': 3,  # 最少卖单数量 - online模式使用
    'SELL_COUNT_BUCKETS': [0, 2, 4, 6, 8, 10, 12, 15],  # 卖单数量分桶边界
    
    # 条件12: 大单占比检查
    # 'off' - 禁用此条件
    # 'online' - 启用此条件，进行实际过滤
    # 'debug' - 调试模式，只收集统计数据，不过滤
    'LARGE_TRADE_RATIO_CHECK_MODE': 'online',  # 可选值: 'off', 'online', 'debug'
    'LARGE_TRADE_RATIO_LOOKBACK': 20,  # 向前查看的交易数量
    'LARGE_TRADE_THRESHOLD': 1.0,  # 大单阈值(SOL)，交易金额绝对值 >= 此值视为大单
    'LARGE_TRADE_RATIO_RANGE': (0.0, 0.1),  # 大单占比范围 - online模式使用
    'LARGE_TRADE_RATIO_BUCKETS': [0.0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0],  # 大单占比分桶边界
    
    # 条件13: 小单占比检查
    # 'off' - 禁用此条件
    # 'online' - 启用此条件，进行实际过滤
    # 'debug' - 调试模式，只收集统计数据，不过滤
    'SMALL_TRADE_RATIO_CHECK_MODE': 'debug',  # 可选值: 'off', 'online', 'debug'
    'SMALL_TRADE_RATIO_LOOKBACK': 20,  # 向前查看的交易数量
    'SMALL_TRADE_THRESHOLD': 0.1,  # 小单阈值(SOL)，交易金额绝对值 < 此值视为小单
    'SMALL_TRADE_RATIO_RANGE': (0.0, 0.3),  # 小单占比范围 - online模式使用
    'SMALL_TRADE_RATIO_BUCKETS': [0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0],  # 小单占比分桶边界
    
    # 条件14: 连续大额买单检查
    # 'off' - 禁用此条件
    # 'online' - 启用此条件，进行实际过滤
    # 'debug' - 调试模式，只收集统计数据，不过滤
    'CONSECUTIVE_BUY_CHECK_MODE': 'debug',  # 可选值: 'off', 'online', 'debug'
    'CONSECUTIVE_BUY_THRESHOLD': 0.0,  # 大额买单阈值(SOL)，交易金额绝对值 >= 此值
    'CONSECUTIVE_BUY_MIN': 3,  # 最少连续买单数量 - online模式使用
    'CONSECUTIVE_BUY_BUCKETS': [0, 1, 2, 3, 4, 5, 7, 10],  # 连续买单数量分桶边界
    
    # 条件15: 连续大额卖单检查
    # 'off' - 禁用此条件
    # 'online' - 启用此条件，进行实际过滤
    # 'debug' - 调试模式，只收集统计数据，不过滤
    'CONSECUTIVE_SELL_CHECK_MODE': 'debug',  # 可选值: 'off', 'online', 'debug'
    'CONSECUTIVE_SELL_THRESHOLD': 0.0,  # 大额卖单阈值(SOL)，交易金额绝对值 >= 此值
    'CONSECUTIVE_SELL_MAX': 2,  # 最多连续卖单数量（超过则不买）- online模式使用
    'CONSECUTIVE_SELL_BUCKETS': [0, 1, 2, 3, 4, 5, 7, 10],  # 连续卖单数量分桶边界
}


SELL_CONDITIONS_CONFIG = {
    # 市值止盈
    'MAX_NOWSOL_SELL': 70.0,  # 当市值 >= 70 SOL 时直接卖出
    
    # 亏损止损
    'LOSS_PERCENTAGE': 0.05,  # 亏损达到 5% 时触发止损检查
    'LOOKBACK_TRADES_FOR_MIN_PRICE': 7,  # 买入前N笔交易用于计算最小价格
    
    # 回撤止损
    'RETRACEMENT_LOW_PROFIT': 0.05,  # 最大盈利 < 50% 时，回撤 3% 卖出
    'RETRACEMENT_HIGH_PROFIT': 0.05,  # 最大盈利 >= 50% 时，回撤 5% 卖出
    'HIGH_PROFIT_THRESHOLD': 0.30,  # 高盈利阈值 50%
    'RETRACEMENT_MIN_COUNT': 3,  # 回撤条件连续满足次数 >= 此值才触发卖出

    # 最大持有时间（秒）
    'MAX_HOLD_TIME_SECONDS': 400,  # 持有超过 400 秒卖出

    # 冷淡期卖出
    'QUIET_PERIOD_ENABLED': True,  # 是否启用冷淡期卖出
    'QUIET_PERIOD_SECONDS': 40,  # 冷淡期时间窗口（秒）
    'QUIET_PERIOD_MIN_AMOUNT': 0.5,  # 冷淡期内没有超过此金额的交易
}


def is_max_amount_in_recent_trades(trade_data: List[Dict], current_index: int, current_amount: float, min_threshold: float, lookback_count: int) -> bool:
    """
    检查当前交易金额绝对值是否为近T单中最大
    
    Args:
        trade_data: 交易数据列表
        current_index: 当前交易索引
        current_amount: 当前交易金额绝对值
        min_threshold: 过滤掉交易金额绝对值小于此值的交易
        lookback_count: 向前查看的交易数量
    
    Returns:
        True如果当前交易金额是最大的，否则False
    """
    filtered_amounts = []
    
    # 从当前交易的前一笔开始向前遍历
    for i in range(current_index - 1, -1, -1):
        try:
            amount = abs(float(trade_data[i].get('tradeamount', 0)))
            # 过滤掉交易金额绝对值小于阈值的交易
            if amount >= min_threshold:
                filtered_amounts.append(amount)
                # 如果已经收集到足够数量的交易，停止遍历
                if len(filtered_amounts) >= lookback_count:
                    break
        except (TypeError, ValueError):
            continue
    
    # 如果没有有效交易，当前交易默认为最大
    if not filtered_amounts:
        return True
    
    # 检查当前交易金额是否大于所有历史交易金额
    return current_amount > max(filtered_amounts)


def get_filtered_trades_sum(trade_data: List[Dict], current_index: int, min_amount: float, count: int) -> Optional[float]:
    """
    获取过滤后的前N笔交易的金额总和
    
    Args:
        trade_data: 交易数据列表
        current_index: 当前交易索引
        min_amount: 过滤掉交易金额绝对值小于此值的交易
        count: 需要取的有效交易数量
    
    Returns:
        交易金额总和，如果有效交易数量不足则返回None
    """
    filtered_amounts = []
    
    # 从当前交易的前一笔开始向前遍历
    for i in range(current_index - 1, -1, -1):
        try:
            amount = float(trade_data[i].get('tradeamount', 0))
            # 过滤掉交易金额绝对值小于阈值的交易
            if abs(amount) >= min_amount:
                filtered_amounts.append(amount)
                # 如果已经收集到足够数量的交易，停止遍历
                if len(filtered_amounts) >= count:
                    break
        except (TypeError, ValueError):
            continue
    
    # 如果有效交易数量不足，返回None
    if len(filtered_amounts) < count:
        return None
    
    return sum(filtered_amounts)


def calculate_volatility(values: List[float]) -> float:
    """
    计算波动率（变异系数 = 标准差/均值）
    
    Args:
        values: 数值列表
    
    Returns:
        波动率值
    """
    if len(values) < 2:
        return 0.0
    
    mean = sum(values) / len(values)
    if mean == 0:
        return 0.0
    
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    std_dev = variance ** 0.5
    return std_dev / abs(mean)  # 变异系数


def get_recent_trades_volatility(trade_data: List[Dict], current_index: int, lookback_count: int, min_amount: float, volatility_type: str) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    获取近N个交易单的价格、时间和金额波动率
    
    Args:
        trade_data: 交易数据列表
        current_index: 当前交易索引
        lookback_count: 向前查看的交易数量
        min_amount: 过滤掉交易金额绝对值小于此值的交易
        volatility_type: 波动率类型 ('price', 'time', 'amount', 'all')
    
    Returns:
        (价格波动率, 时间波动率, 金额波动率) 元组，如果交易数量不足则返回 (None, None, None)
    """
    prices = []
    time_intervals = []
    amounts = []
    
    # 从当前交易的前一笔开始向前遍历，过滤后取N笔有效交易
    prev_time = None
    valid_count = 0
    
    for i in range(current_index - 1, -1, -1):
        if valid_count >= lookback_count:
            break
        
        try:
            # 过滤交易金额绝对值小于阈值的交易
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
                        # 计算时间间隔（毫秒）
                        time_intervals.append(prev_time - tradetime)  # 因为是倒序遍历
                    prev_time = tradetime
            
            if volatility_type in ('amount', 'all'):
                amounts.append(amount)
        except (TypeError, ValueError):
            continue
    
    price_volatility = None
    time_volatility = None
    amount_volatility = None
    
    if volatility_type in ('price', 'all') and len(prices) >= 2:
        price_volatility = calculate_volatility(prices)
    
    if volatility_type in ('time', 'all') and len(time_intervals) >= 2:
        time_volatility = calculate_volatility(time_intervals)
    
    if volatility_type in ('amount', 'all') and len(amounts) >= 2:
        amount_volatility = calculate_volatility(amounts)
    
    return price_volatility, time_volatility, amount_volatility


def get_price_ratio_to_min(trade_data: List[Dict], current_index: int, current_price: float, lookback_count: int) -> Optional[float]:
    """
    获取当前价格相对于近N单最低价的涨幅百分比
    
    Args:
        trade_data: 交易数据列表
        current_index: 当前交易索引
        current_price: 当前交易价格
        lookback_count: 向前查看的交易数量
    
    Returns:
        涨幅百分比 (当前价格/最低价 - 1) * 100，如果数据不足则返回None
    """
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
    
    return (current_price / min_price - 1) * 100  # 涨幅百分比


def get_buy_sell_count(trade_data: List[Dict], current_index: int, lookback_count: int) -> Tuple[int, int]:
    """
    获取近N个交易单里的买单和卖单数量
    
    Args:
        trade_data: 交易数据列表
        current_index: 当前交易索引
        lookback_count: 向前查看的交易数量
    
    Returns:
        (买单数量, 卖单数量) 元组
    """
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


def get_large_small_trade_ratio(trade_data: List[Dict], current_index: int, lookback_count: int, large_threshold: float, small_threshold: float) -> Tuple[float, float]:
    """
    获取近N个交易单里大单和小单的占比
    
    Args:
        trade_data: 交易数据列表
        current_index: 当前交易索引
        lookback_count: 向前查看的交易数量
        large_threshold: 大单阈值(SOL)，交易金额绝对值 >= 此值视为大单
        small_threshold: 小单阈值(SOL)，交易金额绝对值 < 此值视为小单
    
    Returns:
        (大单占比, 小单占比) 元组
    """
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


def get_consecutive_buy_sell_count(trade_data: List[Dict], current_index: int, buy_threshold: float, sell_threshold: float) -> Tuple[int, int]:
    """
    获取从当前位置向前连续大额买单和卖单的数量
    
    Args:
        trade_data: 交易数据列表
        current_index: 当前交易索引
        buy_threshold: 大额买单阈值(SOL)，交易金额绝对值 >= 此值
        sell_threshold: 大额卖单阈值(SOL)，交易金额绝对值 >= 此值
    
    Returns:
        (连续买单数量, 连续卖单数量) 元组
    """
    consecutive_buy = 0
    consecutive_sell = 0
    
    # 计算连续买单数量
    for i in range(current_index - 1, -1, -1):
        try:
            tradeamount = float(trade_data[i].get('tradeamount', 0))
            abs_amount = abs(tradeamount)
            # 如果是大额买单，继续计数
            if tradeamount > 0 and abs_amount >= buy_threshold:
                consecutive_buy += 1
            else:
                break  # 遇到非大额买单就停止
        except (TypeError, ValueError):
            break
    
    # 计算连续卖单数量
    for i in range(current_index - 1, -1, -1):
        try:
            tradeamount = float(trade_data[i].get('tradeamount', 0))
            abs_amount = abs(tradeamount)
            # 如果是大额卖单，继续计数
            if tradeamount < 0 and abs_amount >= sell_threshold:
                consecutive_sell += 1
            else:
                break  # 遇到非大额卖单就停止
        except (TypeError, ValueError):
            break
    
    return consecutive_buy, consecutive_sell


# Debug模式统计数据收集器
class DebugStatsCollector:
    """收集debug模式下的统计数据"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """重置统计数据"""
        # 条件4: 时间差检查统计
        self.time_diff_stats = {
            'total': 0,
            'time_diff_values': [],  # 所有时间差值
            'profitable_time_diff_values': [],  # 盈利交易的时间差值
            'profit_rates_by_time_diff': {},  # 按时间差分桶记录盈利率 {bucket_name: [profit_rate, ...]}
        }
        
        # 条件7: 最大金额检查统计
        self.max_amount_stats = {
            'total': 0,
            'is_max': 0,
            'not_max': 0,
            'profitable_is_max': 0,
            'profitable_not_max': 0,
            'profit_rates_is_max': [],  # 是最大金额的盈利率列表
            'profit_rates_not_max': [],  # 不是最大金额的盈利率列表
        }
        
        # 条件8: 波动率检查统计
        self.volatility_stats = {
            'total': 0,
            'price_volatility_values': [],  # 所有价格波动率值
            'time_volatility_values': [],   # 所有时间波动率值
            'amount_volatility_values': [],  # 所有金额波动率值
            'profitable_price_volatility_values': [],  # 盈利交易的价格波动率值
            'profitable_time_volatility_values': [],   # 盈利交易的时间波动率值
            'profitable_amount_volatility_values': [],  # 盈利交易的金额波动率值
            'profit_rates_by_price_volatility': {},  # 按价格波动率分桶记录盈利率
            'profit_rates_by_time_volatility': {},   # 按时间波动率分桶记录盈利率
            'profit_rates_by_amount_volatility': {},  # 按金额波动率分桶记录盈利率
        }
        
        # 条件9: 价格比例检查统计
        self.price_ratio_stats = {
            'total': 0,
            'price_ratio_values': [],  # 所有价格比例值
            'profitable_price_ratio_values': [],  # 盈利交易的价格比例值
        }
        
        # 条件10: 买单数量检查统计
        self.buy_count_stats = {
            'total': 0,
            'buy_count_values': [],  # 所有买单数量值
            'profitable_buy_count_values': [],  # 盈利交易的买单数量值
        }
        
        # 条件11: 卖单数量检查统计
        self.sell_count_stats = {
            'total': 0,
            'sell_count_values': [],  # 所有卖单数量值
            'profitable_sell_count_values': [],  # 盈利交易的卖单数量值
        }
        
        # 条件12: 大单占比检查统计
        self.large_trade_ratio_stats = {
            'total': 0,
            'large_trade_ratio_values': [],  # 所有大单占比值
            'profitable_large_trade_ratio_values': [],  # 盈利交易的大单占比值
        }
        
        # 条件13: 小单占比检查统计
        self.small_trade_ratio_stats = {
            'total': 0,
            'small_trade_ratio_values': [],  # 所有小单占比值
            'profitable_small_trade_ratio_values': [],  # 盈利交易的小单占比值
        }
        
        # 条件14: 连续大额买单检查统计
        self.consecutive_buy_stats = {
            'total': 0,
            'consecutive_buy_values': [],  # 所有连续买单数量值
            'profitable_consecutive_buy_values': [],  # 盈利交易的连续买单数量值
        }
        
        # 条件15: 连续大额卖单检查统计
        self.consecutive_sell_stats = {
            'total': 0,
            'consecutive_sell_values': [],  # 所有连续卖单数量值
            'profitable_consecutive_sell_values': [],  # 盈利交易的连续卖单数量值
        }
        
        # 交易记录（用于后续分析）
        self.trade_records = []
        
        # 当前信号的debug信息（用于后续记录交易结果）
        self.current_signal_info = {
            'is_max_amount': None,
            'price_variance': None,
            'time_variance': None,
        }
    
    def record_max_amount_check(self, is_max: bool):
        """记录最大金额检查结果"""
        self.max_amount_stats['total'] += 1
        if is_max:
            self.max_amount_stats['is_max'] += 1
        else:
            self.max_amount_stats['not_max'] += 1
    
    def record_time_diff_check(self, time_diff: int):
        """记录时间差检查结果"""
        self.time_diff_stats['total'] += 1
        self.time_diff_stats['time_diff_values'].append(time_diff)
    
    def record_volatility_check(self, price_volatility: Optional[float], time_volatility: Optional[float], amount_volatility: Optional[float]):
        """记录波动率检查结果"""
        self.volatility_stats['total'] += 1
        if price_volatility is not None:
            self.volatility_stats['price_volatility_values'].append(price_volatility)
        if time_volatility is not None:
            self.volatility_stats['time_volatility_values'].append(time_volatility)
        if amount_volatility is not None:
            self.volatility_stats['amount_volatility_values'].append(amount_volatility)
    
    def record_price_ratio_check(self, price_ratio: float):
        """记录价格比例检查结果"""
        self.price_ratio_stats['total'] += 1
        self.price_ratio_stats['price_ratio_values'].append(price_ratio)
    
    def record_buy_count_check(self, buy_count: int):
        """记录买单数量检查结果"""
        self.buy_count_stats['total'] += 1
        self.buy_count_stats['buy_count_values'].append(buy_count)
    
    def record_sell_count_check(self, sell_count: int):
        """记录卖单数量检查结果"""
        self.sell_count_stats['total'] += 1
        self.sell_count_stats['sell_count_values'].append(sell_count)
    
    def record_large_trade_ratio_check(self, large_ratio: float):
        """记录大单占比检查结果"""
        self.large_trade_ratio_stats['total'] += 1
        self.large_trade_ratio_stats['large_trade_ratio_values'].append(large_ratio)
    
    def record_small_trade_ratio_check(self, small_ratio: float):
        """记录小单占比检查结果"""
        self.small_trade_ratio_stats['total'] += 1
        self.small_trade_ratio_stats['small_trade_ratio_values'].append(small_ratio)
    
    def record_consecutive_buy_check(self, consecutive_buy: int):
        """记录连续买单检查结果"""
        self.consecutive_buy_stats['total'] += 1
        self.consecutive_buy_stats['consecutive_buy_values'].append(consecutive_buy)
    
    def record_consecutive_sell_check(self, consecutive_sell: int):
        """记录连续卖单检查结果"""
        self.consecutive_sell_stats['total'] += 1
        self.consecutive_sell_stats['consecutive_sell_values'].append(consecutive_sell)
    
    def record_trade_result(self, is_profitable: bool, time_diff: Optional[int], is_max: Optional[bool], price_volatility: Optional[float], time_volatility: Optional[float], amount_volatility: Optional[float], price_ratio: Optional[float] = None, buy_count: Optional[int] = None, sell_count: Optional[int] = None, large_trade_ratio: Optional[float] = None, small_trade_ratio: Optional[float] = None, consecutive_buy: Optional[int] = None, consecutive_sell: Optional[int] = None, profit_rate: Optional[float] = None):
        """记录交易结果"""
        self.trade_records.append({
            'is_profitable': is_profitable,
            'time_diff': time_diff,
            'is_max': is_max,
            'price_volatility': price_volatility,
            'time_volatility': time_volatility,
            'amount_volatility': amount_volatility,
            'price_ratio': price_ratio,
            'buy_count': buy_count,
            'sell_count': sell_count,
            'large_trade_ratio': large_trade_ratio,
            'small_trade_ratio': small_trade_ratio,
            'consecutive_buy': consecutive_buy,
            'consecutive_sell': consecutive_sell,
            'profit_rate': profit_rate,
        })
        
        if is_profitable:
            # 时间差统计
            if time_diff is not None:
                self.time_diff_stats['profitable_time_diff_values'].append(time_diff)
            
            # 最大金额统计
            if is_max is True:
                self.max_amount_stats['profitable_is_max'] += 1
            elif is_max is False:
                self.max_amount_stats['profitable_not_max'] += 1
            
            # 波动率统计
            if price_volatility is not None:
                self.volatility_stats['profitable_price_volatility_values'].append(price_volatility)
            if time_volatility is not None:
                self.volatility_stats['profitable_time_volatility_values'].append(time_volatility)
            if amount_volatility is not None:
                self.volatility_stats['profitable_amount_volatility_values'].append(amount_volatility)
            
            # 价格比例统计
            if price_ratio is not None:
                self.price_ratio_stats['profitable_price_ratio_values'].append(price_ratio)
            
            # 买卖单数量统计
            if buy_count is not None:
                self.buy_count_stats['profitable_buy_count_values'].append(buy_count)
            if sell_count is not None:
                self.sell_count_stats['profitable_sell_count_values'].append(sell_count)
            
            # 大小单占比统计
            if large_trade_ratio is not None:
                self.large_trade_ratio_stats['profitable_large_trade_ratio_values'].append(large_trade_ratio)
            if small_trade_ratio is not None:
                self.small_trade_ratio_stats['profitable_small_trade_ratio_values'].append(small_trade_ratio)
            
            # 连续买卖单统计
            if consecutive_buy is not None:
                self.consecutive_buy_stats['profitable_consecutive_buy_values'].append(consecutive_buy)
            if consecutive_sell is not None:
                self.consecutive_sell_stats['profitable_consecutive_sell_values'].append(consecutive_sell)
    
    def get_bucket_distribution(self, values: List[float], buckets: List[float]) -> Dict[str, Dict]:
        """计算值在各分桶中的分布"""
        if not values:
            return {}
        
        distribution = {}
        total = len(values)
        
        for i in range(len(buckets)):
            if i == len(buckets) - 1:
                # 最后一个桶: >= buckets[i]
                bucket_name = f">={buckets[i]}"
                count = sum(1 for v in values if v >= buckets[i])
            else:
                # 中间桶: [buckets[i], buckets[i+1])
                bucket_name = f"[{buckets[i]}, {buckets[i+1]})"
                count = sum(1 for v in values if buckets[i] <= v < buckets[i+1])
            
            distribution[bucket_name] = {
                'count': count,
                'ratio': count / total if total > 0 else 0,
            }
        
        return distribution
    
    def get_bucket_for_value(self, value: float, buckets: List[float]) -> str:
        """获取值所属的分桶名称"""
        for i in range(len(buckets)):
            if i == len(buckets) - 1:
                return f">={buckets[i]}"
            elif buckets[i] <= value < buckets[i+1]:
                return f"[{buckets[i]}, {buckets[i+1]})"
        return f">={buckets[-1]}"
    
    def get_avg_profit_rate_by_bucket(self, values: List[float], buckets: List[float], all_records: List[Dict], value_key: str) -> Dict[str, float]:
        """按分桶计算平均盈利率"""
        bucket_profit_rates: Dict[str, List[float]] = {}
        
        for record in all_records:
            value = record.get(value_key)
            profit_rate = record.get('profit_rate')
            if value is not None and profit_rate is not None:
                bucket_name = self.get_bucket_for_value(value, buckets)
                if bucket_name not in bucket_profit_rates:
                    bucket_profit_rates[bucket_name] = []
                bucket_profit_rates[bucket_name].append(profit_rate)
        
        avg_profit_rates = {}
        for bucket_name, rates in bucket_profit_rates.items():
            avg_profit_rates[bucket_name] = sum(rates) / len(rates) if rates else 0.0
        
        return avg_profit_rates
    
    def print_summary(self):
        """打印统计摘要"""
        print("\n" + "=" * 60)
        print("Debug模式统计摘要")
        print("=" * 60)
        
        # 计算总体平均盈利率
        all_profit_rates = [r.get('profit_rate', 0) for r in self.trade_records if r.get('profit_rate') is not None]
        overall_avg_profit_rate = sum(all_profit_rates) / len(all_profit_rates) * 100 if all_profit_rates else 0
        
        # 条件4: 时间差检查统计
        if self.time_diff_stats['total'] > 0:
            total = self.time_diff_stats['total']
            profitable_count = len(self.time_diff_stats['profitable_time_diff_values'])
            
            print("\n【条件4: 时间差检查】")
            print(f"  总交易数: {total}, 盈利: {profitable_count}, 盈利率: {profitable_count/total*100:.2f}%, 平均盈利率: {overall_avg_profit_rate:.2f}%")
            
            # 时间差分布
            if self.time_diff_stats['time_diff_values']:
                print(f"\n  时间差分布:")
                time_diff_buckets = BUY_CONDITIONS_CONFIG['TIME_DIFF_BUCKETS']
                time_diff_dist = self.get_bucket_distribution(self.time_diff_stats['time_diff_values'], time_diff_buckets)
                
                # 计算每个分桶的盈利数量和平均盈利率
                profitable_time_diff_dist = self.get_bucket_distribution(self.time_diff_stats['profitable_time_diff_values'], time_diff_buckets) if self.time_diff_stats['profitable_time_diff_values'] else {}
                avg_profit_rates = self.get_avg_profit_rate_by_bucket(self.time_diff_stats['time_diff_values'], time_diff_buckets, self.trade_records, 'time_diff')
                
                for bucket_name, stats in time_diff_dist.items():
                    profitable_in_bucket = profitable_time_diff_dist.get(bucket_name, {'count': 0})['count']
                    bucket_profit_rate = profitable_in_bucket / stats['count'] * 100 if stats['count'] > 0 else 0
                    avg_rate = avg_profit_rates.get(bucket_name, 0) * 100
                    print(f"    {bucket_name}: {stats['count']} ({stats['ratio']*100:.2f}%) | 盈利: {profitable_in_bucket} ({bucket_profit_rate:.2f}%) | 平均盈利率: {avg_rate:.2f}%")
        
        # 条件7: 最大金额检查统计
        if self.max_amount_stats['total'] > 0:
            total = self.max_amount_stats['total']
            is_max = self.max_amount_stats['is_max']
            not_max = self.max_amount_stats['not_max']
            profitable_is_max = self.max_amount_stats['profitable_is_max']
            profitable_not_max = self.max_amount_stats['profitable_not_max']
            
            # 计算是/不是最大金额的平均盈利率
            is_max_rates = [r.get('profit_rate', 0) for r in self.trade_records if r.get('is_max') is True and r.get('profit_rate') is not None]
            not_max_rates = [r.get('profit_rate', 0) for r in self.trade_records if r.get('is_max') is False and r.get('profit_rate') is not None]
            avg_is_max_rate = sum(is_max_rates) / len(is_max_rates) * 100 if is_max_rates else 0
            avg_not_max_rate = sum(not_max_rates) / len(not_max_rates) * 100 if not_max_rates else 0
            
            print("\n【条件7: 最大金额检查】")
            print(f"  总交易数: {total}, 平均盈利率: {overall_avg_profit_rate:.2f}%")
            if is_max > 0:
                print(f"  是最大金额: {is_max} ({is_max/total*100:.2f}%) | 盈利: {profitable_is_max} ({profitable_is_max/is_max*100:.2f}%) | 平均盈利率: {avg_is_max_rate:.2f}%")
            if not_max > 0:
                print(f"  不是最大金额: {not_max} ({not_max/total*100:.2f}%) | 盈利: {profitable_not_max} ({profitable_not_max/not_max*100:.2f}%) | 平均盈利率: {avg_not_max_rate:.2f}%")
        
        # 条件8: 波动率检查统计
        if self.volatility_stats['total'] > 0:
            total = self.volatility_stats['total']
            profitable_price_count = len(self.volatility_stats['profitable_price_volatility_values'])
            profitable_time_count = len(self.volatility_stats['profitable_time_volatility_values'])
            profitable_amount_count = len(self.volatility_stats['profitable_amount_volatility_values'])
            
            print("\n【条件8: 波动率检查】")
            print(f"  总交易数: {total}, 平均盈利率: {overall_avg_profit_rate:.2f}%")
            
            # 价格波动率分布
            if self.volatility_stats['price_volatility_values']:
                all_count = len(self.volatility_stats['price_volatility_values'])
                print(f"\n  价格波动率分布 (所有交易: {all_count}, 盈利: {profitable_price_count}, 盈利率: {profitable_price_count/all_count*100:.2f}%):")
                price_buckets = BUY_CONDITIONS_CONFIG['PRICE_VOLATILITY_BUCKETS']
                price_dist = self.get_bucket_distribution(self.volatility_stats['price_volatility_values'], price_buckets)
                
                # 计算每个分桶的盈利数量和平均盈利率
                profitable_price_dist = self.get_bucket_distribution(self.volatility_stats['profitable_price_volatility_values'], price_buckets) if self.volatility_stats['profitable_price_volatility_values'] else {}
                avg_profit_rates = self.get_avg_profit_rate_by_bucket(self.volatility_stats['price_volatility_values'], price_buckets, self.trade_records, 'price_volatility')
                
                for bucket_name, stats in price_dist.items():
                    profitable_in_bucket = profitable_price_dist.get(bucket_name, {'count': 0})['count']
                    bucket_profit_rate = profitable_in_bucket / stats['count'] * 100 if stats['count'] > 0 else 0
                    avg_rate = avg_profit_rates.get(bucket_name, 0) * 100
                    print(f"    {bucket_name}: {stats['count']} ({stats['ratio']*100:.2f}%) | 盈利: {profitable_in_bucket} ({bucket_profit_rate:.2f}%) | 平均盈利率: {avg_rate:.2f}%")
            
            # 时间波动率分布
            if self.volatility_stats['time_volatility_values']:
                all_count = len(self.volatility_stats['time_volatility_values'])
                print(f"\n  时间波动率分布 (所有交易: {all_count}, 盈利: {profitable_time_count}, 盈利率: {profitable_time_count/all_count*100:.2f}%):")
                time_buckets = BUY_CONDITIONS_CONFIG['TIME_VOLATILITY_BUCKETS']
                time_dist = self.get_bucket_distribution(self.volatility_stats['time_volatility_values'], time_buckets)
                
                # 计算每个分桶的盈利数量和平均盈利率
                profitable_time_dist = self.get_bucket_distribution(self.volatility_stats['profitable_time_volatility_values'], time_buckets) if self.volatility_stats['profitable_time_volatility_values'] else {}
                avg_profit_rates = self.get_avg_profit_rate_by_bucket(self.volatility_stats['time_volatility_values'], time_buckets, self.trade_records, 'time_volatility')
                
                for bucket_name, stats in time_dist.items():
                    profitable_in_bucket = profitable_time_dist.get(bucket_name, {'count': 0})['count']
                    bucket_profit_rate = profitable_in_bucket / stats['count'] * 100 if stats['count'] > 0 else 0
                    avg_rate = avg_profit_rates.get(bucket_name, 0) * 100
                    print(f"    {bucket_name}: {stats['count']} ({stats['ratio']*100:.2f}%) | 盈利: {profitable_in_bucket} ({bucket_profit_rate:.2f}%) | 平均盈利率: {avg_rate:.2f}%")
            
            # 金额波动率分布
            if self.volatility_stats['amount_volatility_values']:
                all_count = len(self.volatility_stats['amount_volatility_values'])
                print(f"\n  金额波动率分布 (所有交易: {all_count}, 盈利: {profitable_amount_count}, 盈利率: {profitable_amount_count/all_count*100:.2f}%):")
                amount_buckets = BUY_CONDITIONS_CONFIG['AMOUNT_VOLATILITY_BUCKETS']
                amount_dist = self.get_bucket_distribution(self.volatility_stats['amount_volatility_values'], amount_buckets)
                
                # 计算每个分桶的盈利数量和平均盈利率
                profitable_amount_dist = self.get_bucket_distribution(self.volatility_stats['profitable_amount_volatility_values'], amount_buckets) if self.volatility_stats['profitable_amount_volatility_values'] else {}
                avg_profit_rates = self.get_avg_profit_rate_by_bucket(self.volatility_stats['amount_volatility_values'], amount_buckets, self.trade_records, 'amount_volatility')
                
                for bucket_name, stats in amount_dist.items():
                    profitable_in_bucket = profitable_amount_dist.get(bucket_name, {'count': 0})['count']
                    bucket_profit_rate = profitable_in_bucket / stats['count'] * 100 if stats['count'] > 0 else 0
                    avg_rate = avg_profit_rates.get(bucket_name, 0) * 100
                    print(f"    {bucket_name}: {stats['count']} ({stats['ratio']*100:.2f}%) | 盈利: {profitable_in_bucket} ({bucket_profit_rate:.2f}%) | 平均盈利率: {avg_rate:.2f}%")
        
        # 条件9: 价格比例检查统计
        if self.price_ratio_stats['total'] > 0:
            total = self.price_ratio_stats['total']
            profitable_count = len(self.price_ratio_stats['profitable_price_ratio_values'])
            
            print("\n【条件9: 价格比例检查】")
            print(f"  总交易数: {total}, 盈利: {profitable_count}, 盈利率: {profitable_count/total*100:.2f}%, 平均盈利率: {overall_avg_profit_rate:.2f}%")
            
            # 价格比例分布
            if self.price_ratio_stats['price_ratio_values']:
                print(f"\n  价格比例分布 (当前价格/近N单最低价 - 1)%:")
                price_ratio_buckets = BUY_CONDITIONS_CONFIG['PRICE_RATIO_BUCKETS']
                price_ratio_dist = self.get_bucket_distribution(self.price_ratio_stats['price_ratio_values'], price_ratio_buckets)
                
                # 计算每个分桶的盈利数量和平均盈利率
                profitable_price_ratio_dist = self.get_bucket_distribution(self.price_ratio_stats['profitable_price_ratio_values'], price_ratio_buckets) if self.price_ratio_stats['profitable_price_ratio_values'] else {}
                avg_profit_rates = self.get_avg_profit_rate_by_bucket(self.price_ratio_stats['price_ratio_values'], price_ratio_buckets, self.trade_records, 'price_ratio')
                
                for bucket_name, stats in price_ratio_dist.items():
                    profitable_in_bucket = profitable_price_ratio_dist.get(bucket_name, {'count': 0})['count']
                    bucket_profit_rate = profitable_in_bucket / stats['count'] * 100 if stats['count'] > 0 else 0
                    avg_rate = avg_profit_rates.get(bucket_name, 0) * 100
                    print(f"    {bucket_name}%: {stats['count']} ({stats['ratio']*100:.2f}%) | 盈利: {profitable_in_bucket} ({bucket_profit_rate:.2f}%) | 平均盈利率: {avg_rate:.2f}%")
        
        # 条件10: 买单数量检查统计
        if self.buy_count_stats['total'] > 0:
            total = self.buy_count_stats['total']
            profitable_count = len(self.buy_count_stats['profitable_buy_count_values'])
            
            print("\n【条件10: 买单数量检查】")
            print(f"  总交易数: {total}, 盈利: {profitable_count}, 盈利率: {profitable_count/total*100:.2f}%, 平均盈利率: {overall_avg_profit_rate:.2f}%")
            
            # 买单数量分布
            if self.buy_count_stats['buy_count_values']:
                print(f"\n  买单数量分布:")
                buy_count_buckets = BUY_CONDITIONS_CONFIG['BUY_COUNT_BUCKETS']
                buy_count_dist = self.get_bucket_distribution(self.buy_count_stats['buy_count_values'], buy_count_buckets)
                
                # 计算每个分桶的盈利数量和平均盈利率
                profitable_buy_count_dist = self.get_bucket_distribution(self.buy_count_stats['profitable_buy_count_values'], buy_count_buckets) if self.buy_count_stats['profitable_buy_count_values'] else {}
                avg_profit_rates = self.get_avg_profit_rate_by_bucket(self.buy_count_stats['buy_count_values'], buy_count_buckets, self.trade_records, 'buy_count')
                
                for bucket_name, stats in buy_count_dist.items():
                    profitable_in_bucket = profitable_buy_count_dist.get(bucket_name, {'count': 0})['count']
                    bucket_profit_rate = profitable_in_bucket / stats['count'] * 100 if stats['count'] > 0 else 0
                    avg_rate = avg_profit_rates.get(bucket_name, 0) * 100
                    print(f"    {bucket_name}: {stats['count']} ({stats['ratio']*100:.2f}%) | 盈利: {profitable_in_bucket} ({bucket_profit_rate:.2f}%) | 平均盈利率: {avg_rate:.2f}%")
        
        # 条件11: 卖单数量检查统计
        if self.sell_count_stats['total'] > 0:
            total = self.sell_count_stats['total']
            profitable_count = len(self.sell_count_stats['profitable_sell_count_values'])
            
            print("\n【条件11: 卖单数量检查】")
            print(f"  总交易数: {total}, 盈利: {profitable_count}, 盈利率: {profitable_count/total*100:.2f}%, 平均盈利率: {overall_avg_profit_rate:.2f}%")
            
            # 卖单数量分布
            if self.sell_count_stats['sell_count_values']:
                print(f"\n  卖单数量分布:")
                sell_count_buckets = BUY_CONDITIONS_CONFIG['SELL_COUNT_BUCKETS']
                sell_count_dist = self.get_bucket_distribution(self.sell_count_stats['sell_count_values'], sell_count_buckets)
                
                # 计算每个分桶的盈利数量和平均盈利率
                profitable_sell_count_dist = self.get_bucket_distribution(self.sell_count_stats['profitable_sell_count_values'], sell_count_buckets) if self.sell_count_stats['profitable_sell_count_values'] else {}
                avg_profit_rates = self.get_avg_profit_rate_by_bucket(self.sell_count_stats['sell_count_values'], sell_count_buckets, self.trade_records, 'sell_count')
                
                for bucket_name, stats in sell_count_dist.items():
                    profitable_in_bucket = profitable_sell_count_dist.get(bucket_name, {'count': 0})['count']
                    bucket_profit_rate = profitable_in_bucket / stats['count'] * 100 if stats['count'] > 0 else 0
                    avg_rate = avg_profit_rates.get(bucket_name, 0) * 100
                    print(f"    {bucket_name}: {stats['count']} ({stats['ratio']*100:.2f}%) | 盈利: {profitable_in_bucket} ({bucket_profit_rate:.2f}%) | 平均盈利率: {avg_rate:.2f}%")
        
        # 条件12: 大单占比检查统计
        if self.large_trade_ratio_stats['total'] > 0:
            total = self.large_trade_ratio_stats['total']
            profitable_count = len(self.large_trade_ratio_stats['profitable_large_trade_ratio_values'])
            
            print("\n【条件12: 大单占比检查】")
            print(f"  总交易数: {total}, 盈利: {profitable_count}, 盈利率: {profitable_count/total*100:.2f}%, 平均盈利率: {overall_avg_profit_rate:.2f}%")
            
            # 大单占比分布
            if self.large_trade_ratio_stats['large_trade_ratio_values']:
                large_threshold = BUY_CONDITIONS_CONFIG['LARGE_TRADE_THRESHOLD']
                print(f"\n  大单(>={large_threshold}SOL)占比分布:")
                large_ratio_buckets = BUY_CONDITIONS_CONFIG['LARGE_TRADE_RATIO_BUCKETS']
                large_ratio_dist = self.get_bucket_distribution(self.large_trade_ratio_stats['large_trade_ratio_values'], large_ratio_buckets)
                
                profitable_large_ratio_dist = self.get_bucket_distribution(self.large_trade_ratio_stats['profitable_large_trade_ratio_values'], large_ratio_buckets) if self.large_trade_ratio_stats['profitable_large_trade_ratio_values'] else {}
                avg_profit_rates = self.get_avg_profit_rate_by_bucket(self.large_trade_ratio_stats['large_trade_ratio_values'], large_ratio_buckets, self.trade_records, 'large_trade_ratio')
                
                for bucket_name, stats in large_ratio_dist.items():
                    profitable_in_bucket = profitable_large_ratio_dist.get(bucket_name, {'count': 0})['count']
                    bucket_profit_rate = profitable_in_bucket / stats['count'] * 100 if stats['count'] > 0 else 0
                    avg_rate = avg_profit_rates.get(bucket_name, 0) * 100
                    print(f"    {bucket_name}: {stats['count']} ({stats['ratio']*100:.2f}%) | 盈利: {profitable_in_bucket} ({bucket_profit_rate:.2f}%) | 平均盈利率: {avg_rate:.2f}%")
        
        # 条件13: 小单占比检查统计
        if self.small_trade_ratio_stats['total'] > 0:
            total = self.small_trade_ratio_stats['total']
            profitable_count = len(self.small_trade_ratio_stats['profitable_small_trade_ratio_values'])
            
            print("\n【条件13: 小单占比检查】")
            print(f"  总交易数: {total}, 盈利: {profitable_count}, 盈利率: {profitable_count/total*100:.2f}%, 平均盈利率: {overall_avg_profit_rate:.2f}%")
            
            # 小单占比分布
            if self.small_trade_ratio_stats['small_trade_ratio_values']:
                small_threshold = BUY_CONDITIONS_CONFIG['SMALL_TRADE_THRESHOLD']
                print(f"\n  小单(<{small_threshold}SOL)占比分布:")
                small_ratio_buckets = BUY_CONDITIONS_CONFIG['SMALL_TRADE_RATIO_BUCKETS']
                small_ratio_dist = self.get_bucket_distribution(self.small_trade_ratio_stats['small_trade_ratio_values'], small_ratio_buckets)
                
                profitable_small_ratio_dist = self.get_bucket_distribution(self.small_trade_ratio_stats['profitable_small_trade_ratio_values'], small_ratio_buckets) if self.small_trade_ratio_stats['profitable_small_trade_ratio_values'] else {}
                avg_profit_rates = self.get_avg_profit_rate_by_bucket(self.small_trade_ratio_stats['small_trade_ratio_values'], small_ratio_buckets, self.trade_records, 'small_trade_ratio')
                
                for bucket_name, stats in small_ratio_dist.items():
                    profitable_in_bucket = profitable_small_ratio_dist.get(bucket_name, {'count': 0})['count']
                    bucket_profit_rate = profitable_in_bucket / stats['count'] * 100 if stats['count'] > 0 else 0
                    avg_rate = avg_profit_rates.get(bucket_name, 0) * 100
                    print(f"    {bucket_name}: {stats['count']} ({stats['ratio']*100:.2f}%) | 盈利: {profitable_in_bucket} ({bucket_profit_rate:.2f}%) | 平均盈利率: {avg_rate:.2f}%")
        
        # 条件14: 连续大额买单检查统计
        if self.consecutive_buy_stats['total'] > 0:
            total = self.consecutive_buy_stats['total']
            profitable_count = len(self.consecutive_buy_stats['profitable_consecutive_buy_values'])
            
            print("\n【条件14: 连续大额买单检查】")
            print(f"  总交易数: {total}, 盈利: {profitable_count}, 盈利率: {profitable_count/total*100:.2f}%, 平均盈利率: {overall_avg_profit_rate:.2f}%")
            
            # 连续买单数量分布
            if self.consecutive_buy_stats['consecutive_buy_values']:
                buy_threshold = BUY_CONDITIONS_CONFIG['CONSECUTIVE_BUY_THRESHOLD']
                print(f"\n  连续大额(>={buy_threshold}SOL)买单数量分布:")
                consecutive_buy_buckets = BUY_CONDITIONS_CONFIG['CONSECUTIVE_BUY_BUCKETS']
                consecutive_buy_dist = self.get_bucket_distribution(self.consecutive_buy_stats['consecutive_buy_values'], consecutive_buy_buckets)
                
                profitable_consecutive_buy_dist = self.get_bucket_distribution(self.consecutive_buy_stats['profitable_consecutive_buy_values'], consecutive_buy_buckets) if self.consecutive_buy_stats['profitable_consecutive_buy_values'] else {}
                avg_profit_rates = self.get_avg_profit_rate_by_bucket(self.consecutive_buy_stats['consecutive_buy_values'], consecutive_buy_buckets, self.trade_records, 'consecutive_buy')
                
                for bucket_name, stats in consecutive_buy_dist.items():
                    profitable_in_bucket = profitable_consecutive_buy_dist.get(bucket_name, {'count': 0})['count']
                    bucket_profit_rate = profitable_in_bucket / stats['count'] * 100 if stats['count'] > 0 else 0
                    avg_rate = avg_profit_rates.get(bucket_name, 0) * 100
                    print(f"    {bucket_name}: {stats['count']} ({stats['ratio']*100:.2f}%) | 盈利: {profitable_in_bucket} ({bucket_profit_rate:.2f}%) | 平均盈利率: {avg_rate:.2f}%")
        
        # 条件15: 连续大额卖单检查统计
        if self.consecutive_sell_stats['total'] > 0:
            total = self.consecutive_sell_stats['total']
            profitable_count = len(self.consecutive_sell_stats['profitable_consecutive_sell_values'])
            
            print("\n【条件15: 连续大额卖单检查】")
            print(f"  总交易数: {total}, 盈利: {profitable_count}, 盈利率: {profitable_count/total*100:.2f}%, 平均盈利率: {overall_avg_profit_rate:.2f}%")
            
            # 连续卖单数量分布
            if self.consecutive_sell_stats['consecutive_sell_values']:
                sell_threshold = BUY_CONDITIONS_CONFIG['CONSECUTIVE_SELL_THRESHOLD']
                print(f"\n  连续大额(>={sell_threshold}SOL)卖单数量分布:")
                consecutive_sell_buckets = BUY_CONDITIONS_CONFIG['CONSECUTIVE_SELL_BUCKETS']
                consecutive_sell_dist = self.get_bucket_distribution(self.consecutive_sell_stats['consecutive_sell_values'], consecutive_sell_buckets)
                
                profitable_consecutive_sell_dist = self.get_bucket_distribution(self.consecutive_sell_stats['profitable_consecutive_sell_values'], consecutive_sell_buckets) if self.consecutive_sell_stats['profitable_consecutive_sell_values'] else {}
                avg_profit_rates = self.get_avg_profit_rate_by_bucket(self.consecutive_sell_stats['consecutive_sell_values'], consecutive_sell_buckets, self.trade_records, 'consecutive_sell')
                
                for bucket_name, stats in consecutive_sell_dist.items():
                    profitable_in_bucket = profitable_consecutive_sell_dist.get(bucket_name, {'count': 0})['count']
                    bucket_profit_rate = profitable_in_bucket / stats['count'] * 100 if stats['count'] > 0 else 0
                    avg_rate = avg_profit_rates.get(bucket_name, 0) * 100
                    print(f"    {bucket_name}: {stats['count']} ({stats['ratio']*100:.2f}%) | 盈利: {profitable_in_bucket} ({bucket_profit_rate:.2f}%) | 平均盈利率: {avg_rate:.2f}%")
        
        print("=" * 60)


# 全局统计收集器
debug_stats = DebugStatsCollector()


def variant_find_buy_signal(trade_data: List[Dict], start_index: int, creation_time: int) -> Optional[int]:
    """
    寻找买入信号
    
    买入条件：
    1. 距离创币时间 >= T 分钟
    2. 当前市值(nowsol) 在指定范围内
    3. 当前交易金额绝对值在指定范围内
    4. 当前交易单距离上一个交易单的时间差在指定范围内
    5. 过滤后的前N笔交易金额总和在指定范围内
    6. 当前交易类型为买入或卖出
    7. 当前交易金额绝对值是近T单中最大
    """
    if start_index < 0 or start_index >= len(trade_data):
        return None
    
    rec = trade_data[start_index]
    
    # 解析必要字段
    try:
        nowsol = float(rec.get('nowsol', 0))
        tradeamount = float(rec.get('tradeamount', 0))
        tradetime = int(rec.get('tradetime', 0))
    except (TypeError, ValueError):
        return None
    
    # 条件1: 检查距离创币时间是否大于指定分钟数
    time_diff_seconds = (tradetime - creation_time) / 1000  # 转换为秒
    time_diff_minutes = time_diff_seconds / 60  # 转换为分钟
    if time_diff_minutes < BUY_CONDITIONS_CONFIG['TIME_FROM_CREATION_MINUTES']:
        return None
    
    # 条件2: 检查当前市值是否在指定范围内
    nowsol_min, nowsol_max = BUY_CONDITIONS_CONFIG['NOWSOL_RANGE']
    if not (nowsol_min <= nowsol <= nowsol_max):
        return None
    
    # 条件3: 检查交易金额绝对值是否在指定范围内
    amount_min, amount_max = BUY_CONDITIONS_CONFIG['TRADE_AMOUNT_RANGE']
    abs_amount = abs(tradeamount)
    if not (amount_min <= abs_amount <= amount_max):
        return None
    
    # 条件4: 检查当前交易单距离上一个交易单的时间差是否在指定范围内
    time_diff_mode = BUY_CONDITIONS_CONFIG['TIME_DIFF_CHECK_MODE']
    time_diff_from_last = None
    
    if start_index > 0:
        prev_rec = trade_data[start_index - 1]
        try:
            prev_tradetime = int(prev_rec.get('tradetime', 0))
            time_diff_from_last = tradetime - prev_tradetime  # 毫秒
            
            if time_diff_mode == 'online':
                # online模式：进行实际过滤
                time_diff_min, time_diff_max = BUY_CONDITIONS_CONFIG['TIME_DIFF_FROM_LAST_TRADE_RANGE']
                if not (time_diff_min <= time_diff_from_last <= time_diff_max):
                    return None
            # debug模式：不在这里记录，统一在 wrapped_backtest_mint 中记录
        except (TypeError, ValueError):
            return None
    else:
        # 如果是第一笔交易，无法计算时间差，跳过
        return None
    
    # 条件5: 检查过滤后的前N笔交易金额总和是否在指定范围内
    min_amount = BUY_CONDITIONS_CONFIG['FILTERED_TRADES_MIN_AMOUNT']
    trades_count = BUY_CONDITIONS_CONFIG['FILTERED_TRADES_COUNT']
    sum_range = BUY_CONDITIONS_CONFIG['FILTERED_TRADES_SUM_RANGE']
    
    filtered_sum = get_filtered_trades_sum(trade_data, start_index, min_amount, trades_count)
    if filtered_sum is None:
        return None  # 有效交易数量不足
    
    sum_min, sum_max = sum_range
    if not (sum_min <= filtered_sum <= sum_max):
        return None
    
    # 条件6: 检查当前交易类型
    trade_type = BUY_CONDITIONS_CONFIG['TRADE_TYPE']
    if trade_type == 'buy':
        # 只匹配买入交易 (tradeamount > 0)
        if tradeamount <= 0:
            return None
    elif trade_type == 'sell':
        # 只匹配卖出交易 (tradeamount < 0)
        if tradeamount >= 0:
            return None
    # trade_type == 'both' 不做限制，买入和卖出都匹配
    
    # 条件7: 检查当前交易金额是否为近T单中最大
    max_amount_mode = BUY_CONDITIONS_CONFIG['MAX_AMOUNT_CHECK_MODE']
    is_max_amount = None
    
    if max_amount_mode in ('online', 'debug'):
        max_amount_threshold = BUY_CONDITIONS_CONFIG['MAX_AMOUNT_MIN_THRESHOLD']
        max_amount_lookback = BUY_CONDITIONS_CONFIG['MAX_AMOUNT_LOOKBACK_COUNT']
        is_max_amount = is_max_amount_in_recent_trades(trade_data, start_index, abs_amount, max_amount_threshold, max_amount_lookback)
        
        if max_amount_mode == 'online':
            # online模式：进行实际过滤
            if not is_max_amount:
                return None
        # debug模式：不在这里记录，统一在 wrapped_backtest_mint 中记录
    
    # 条件8: 检查近N个交易单的时间或价格波动率是否满足条件
    price_volatility_mode = BUY_CONDITIONS_CONFIG['PRICE_VOLATILITY_CHECK_MODE']
    time_volatility_mode = BUY_CONDITIONS_CONFIG['TIME_VOLATILITY_CHECK_MODE']
    amount_volatility_mode = BUY_CONDITIONS_CONFIG['AMOUNT_VOLATILITY_CHECK_MODE']
    price_volatility = None
    time_volatility = None
    amount_volatility = None
    
    # 判断需要计算哪些波动率
    need_price = price_volatility_mode in ('online', 'debug')
    need_time = time_volatility_mode in ('online', 'debug')
    need_amount = amount_volatility_mode in ('online', 'debug')
    
    if need_price or need_time or need_amount:
        volatility_lookback = BUY_CONDITIONS_CONFIG['VOLATILITY_LOOKBACK_COUNT']
        volatility_min_amount = BUY_CONDITIONS_CONFIG['VOLATILITY_MIN_AMOUNT']
        
        # 根据需要计算的波动率类型构建 volatility_type
        volatility_type = 'all'  # 默认计算全部
        
        price_volatility, time_volatility, amount_volatility = get_recent_trades_volatility(trade_data, start_index, volatility_lookback, volatility_min_amount, volatility_type)
        
        # 条件8a: 价格波动率
        if price_volatility_mode == 'online':
            price_vol_min, price_vol_max = BUY_CONDITIONS_CONFIG['PRICE_VOLATILITY_RANGE']
            if price_volatility is None or not (price_vol_min <= price_volatility <= price_vol_max):
                return None
        
        # 条件8b: 时间波动率
        if time_volatility_mode == 'online':
            time_vol_min, time_vol_max = BUY_CONDITIONS_CONFIG['TIME_VOLATILITY_RANGE']
            if time_volatility is None or not (time_vol_min <= time_volatility <= time_vol_max):
                return None
        
        # 条件8c: 金额波动率
        if amount_volatility_mode == 'online':
            amount_vol_min, amount_vol_max = BUY_CONDITIONS_CONFIG['AMOUNT_VOLATILITY_RANGE']
            if amount_volatility is None or not (amount_vol_min <= amount_volatility <= amount_vol_max):
                return None
        
        # debug模式：不在这里记录，统一在 wrapped_backtest_mint 中记录
    
    # 条件9: 检查当前价格/近N单最低价的比例是否在指定范围内
    price_ratio_mode = BUY_CONDITIONS_CONFIG['PRICE_RATIO_CHECK_MODE']
    price_ratio = None
    
    if price_ratio_mode in ('online', 'debug'):
        price_ratio_lookback = BUY_CONDITIONS_CONFIG['PRICE_RATIO_LOOKBACK_COUNT']
        price_ratio_range = BUY_CONDITIONS_CONFIG['PRICE_RATIO_RANGE']
        
        try:
            current_price = float(rec.get('price', 0))
            if current_price > 0:
                price_ratio = get_price_ratio_to_min(trade_data, start_index, current_price, price_ratio_lookback)
                
                if price_ratio is not None and price_ratio_mode == 'online':
                    # online模式：进行实际过滤
                    ratio_min, ratio_max = price_ratio_range
                    if not (ratio_min <= price_ratio <= ratio_max):
                        return None
                # debug模式：不在这里记录，统一在 wrapped_backtest_mint 中记录
        except (TypeError, ValueError):
            pass
    
    # 条件10: 检查近T个交易单里买单数量是否满足条件
    buy_count_mode = BUY_CONDITIONS_CONFIG['BUY_COUNT_CHECK_MODE']
    sell_count_mode = BUY_CONDITIONS_CONFIG['SELL_COUNT_CHECK_MODE']
    buy_count = None
    sell_count = None
    
    if buy_count_mode in ('online', 'debug'):
        buy_count_lookback = BUY_CONDITIONS_CONFIG['BUY_COUNT_LOOKBACK_COUNT']
        buy_count, _ = get_buy_sell_count(trade_data, start_index, buy_count_lookback)
        
        if buy_count_mode == 'online':
            buy_count_min = BUY_CONDITIONS_CONFIG['BUY_COUNT_MIN']
            if buy_count < buy_count_min:
                return None
        # debug模式：不在这里记录，统一在 wrapped_backtest_mint 中记录
    
    # 条件11: 检查近T个交易单里卖单数量是否满足条件
    if sell_count_mode in ('online', 'debug'):
        sell_count_lookback = BUY_CONDITIONS_CONFIG['SELL_COUNT_LOOKBACK_COUNT']
        _, sell_count = get_buy_sell_count(trade_data, start_index, sell_count_lookback)
        
        if sell_count_mode == 'online':
            sell_count_min = BUY_CONDITIONS_CONFIG['SELL_COUNT_MIN']
            if sell_count < sell_count_min:
                return None
        # debug模式：不在这里记录，统一在 wrapped_backtest_mint 中记录
    
    # 条件12: 检查近N个交易单里大单占比是否在指定范围内
    large_ratio_mode = BUY_CONDITIONS_CONFIG['LARGE_TRADE_RATIO_CHECK_MODE']
    large_trade_ratio = None
    small_trade_ratio = None
    
    if large_ratio_mode in ('online', 'debug') or BUY_CONDITIONS_CONFIG['SMALL_TRADE_RATIO_CHECK_MODE'] in ('online', 'debug'):
        large_lookback = BUY_CONDITIONS_CONFIG['LARGE_TRADE_RATIO_LOOKBACK']
        small_lookback = BUY_CONDITIONS_CONFIG['SMALL_TRADE_RATIO_LOOKBACK']
        large_threshold = BUY_CONDITIONS_CONFIG['LARGE_TRADE_THRESHOLD']
        small_threshold = BUY_CONDITIONS_CONFIG['SMALL_TRADE_THRESHOLD']
        
        # 使用较大的lookback来获取两个占比
        max_lookback = max(large_lookback, small_lookback)
        large_trade_ratio, small_trade_ratio = get_large_small_trade_ratio(trade_data, start_index, max_lookback, large_threshold, small_threshold)
        
        if large_ratio_mode == 'online':
            ratio_min, ratio_max = BUY_CONDITIONS_CONFIG['LARGE_TRADE_RATIO_RANGE']
            if not (ratio_min <= large_trade_ratio <= ratio_max):
                return None
        # debug模式：不在这里记录，统一在 wrapped_backtest_mint 中记录
    
    # 条件13: 检查近N个交易单里小单占比是否在指定范围内
    small_ratio_mode = BUY_CONDITIONS_CONFIG['SMALL_TRADE_RATIO_CHECK_MODE']
    
    if small_ratio_mode == 'online':
        if small_trade_ratio is None:
            small_lookback = BUY_CONDITIONS_CONFIG['SMALL_TRADE_RATIO_LOOKBACK']
            small_threshold = BUY_CONDITIONS_CONFIG['SMALL_TRADE_THRESHOLD']
            _, small_trade_ratio = get_large_small_trade_ratio(trade_data, start_index, small_lookback, 999999, small_threshold)
        
        ratio_min, ratio_max = BUY_CONDITIONS_CONFIG['SMALL_TRADE_RATIO_RANGE']
        if not (ratio_min <= small_trade_ratio <= ratio_max):
            return None
    # debug模式：不在这里记录，统一在 wrapped_backtest_mint 中记录
    
    # 条件14: 检查连续大额买单数量是否满足条件
    consecutive_buy_mode = BUY_CONDITIONS_CONFIG['CONSECUTIVE_BUY_CHECK_MODE']
    consecutive_sell_mode = BUY_CONDITIONS_CONFIG['CONSECUTIVE_SELL_CHECK_MODE']
    consecutive_buy = None
    consecutive_sell = None
    
    if consecutive_buy_mode in ('online', 'debug') or consecutive_sell_mode in ('online', 'debug'):
        buy_threshold = BUY_CONDITIONS_CONFIG['CONSECUTIVE_BUY_THRESHOLD']
        sell_threshold = BUY_CONDITIONS_CONFIG['CONSECUTIVE_SELL_THRESHOLD']
        consecutive_buy, consecutive_sell = get_consecutive_buy_sell_count(trade_data, start_index, buy_threshold, sell_threshold)
        
        if consecutive_buy_mode == 'online':
            min_consecutive = BUY_CONDITIONS_CONFIG['CONSECUTIVE_BUY_MIN']
            if consecutive_buy < min_consecutive:
                return None
        # debug模式：不在这里记录，统一在 wrapped_backtest_mint 中记录
    
    # 条件15: 检查连续大额卖单数量是否满足条件
    if consecutive_sell_mode == 'online':
        max_consecutive = BUY_CONDITIONS_CONFIG['CONSECUTIVE_SELL_MAX']
        if consecutive_sell > max_consecutive:
            return None
    # debug模式：不在这里记录，统一在 wrapped_backtest_mint 中记录
    
    # 保存debug信息供后续记录交易结果使用
    has_debug = (max_amount_mode == 'debug' or 
                 price_volatility_mode == 'debug' or time_volatility_mode == 'debug' or amount_volatility_mode == 'debug' or 
                 price_ratio_mode == 'debug' or buy_count_mode == 'debug' or sell_count_mode == 'debug' or
                 large_ratio_mode == 'debug' or small_ratio_mode == 'debug' or
                 consecutive_buy_mode == 'debug' or consecutive_sell_mode == 'debug')
    if has_debug:
        # 将当前信号的debug信息存储到全局变量
        debug_stats.current_signal_info = {
            'is_max_amount': is_max_amount,
            'price_volatility': price_volatility,
            'time_volatility': time_volatility,
            'amount_volatility': amount_volatility,
            'price_ratio': price_ratio,
            'buy_count': buy_count,
            'sell_count': sell_count,
        }
    
    return start_index


def get_min_price_before_buy(trade_data: List[Dict], buy_index: int, lookback_count: int) -> Optional[float]:
    """
    获取买入点之前N笔交易的最小价格
    
    Args:
        trade_data: 交易数据列表
        buy_index: 买入点索引
        lookback_count: 向前查看的交易数量
    
    Returns:
        最小价格，如果交易数量不足则返回None
    """
    prices = []
    start_index = max(0, buy_index - lookback_count)
    
    for i in range(start_index, buy_index):
        try:
            price = float(trade_data[i].get('price', 0))
            if price > 0:
                prices.append(price)
        except (TypeError, ValueError):
            continue
    
    if not prices:
        return None
    
    return min(prices)


def variant_find_sell_signal(trade_data: List[Dict], buy_index: int, buy_price: float, buy_time: int) -> Tuple[int, str]:
    """
    寻找卖出信号
    
    卖出策略：
    1. 当市值 >= X SOL 时直接卖出
    2. 当亏损达到X%，且当前价格小于买入前7笔交易的最小价格时，直接卖出
    3. 当最大盈利 < 50% 时，回撤达到 3% 直接卖出
    4. 当最大盈利 >= 50% 时，回撤达到 5% 直接卖出
    5. 持有超过最大持有时间则卖出
    6. 冷淡期卖出：近N秒内没有超过X金额的交易，遇到卖单就卖出
    7. 遍历到最后还没有卖出，则强制卖出
    """
    original_buy_price = buy_price  # 原始买入价格
    max_price = buy_price  # 记录持有期间的最高价格
    max_profit_rate = 0.0  # 记录最大盈利率
    
    # 获取配置
    max_nowsol_sell = SELL_CONDITIONS_CONFIG['MAX_NOWSOL_SELL']
    loss_percentage = SELL_CONDITIONS_CONFIG['LOSS_PERCENTAGE']
    lookback_count = SELL_CONDITIONS_CONFIG['LOOKBACK_TRADES_FOR_MIN_PRICE']
    retracement_low = SELL_CONDITIONS_CONFIG['RETRACEMENT_LOW_PROFIT']
    retracement_high = SELL_CONDITIONS_CONFIG['RETRACEMENT_HIGH_PROFIT']
    high_profit_threshold = SELL_CONDITIONS_CONFIG['HIGH_PROFIT_THRESHOLD']
    retracement_min_count = SELL_CONDITIONS_CONFIG.get('RETRACEMENT_MIN_COUNT', 1)
    max_hold_seconds = SELL_CONDITIONS_CONFIG['MAX_HOLD_TIME_SECONDS']
    
    # 冷淡期配置
    quiet_period_enabled = SELL_CONDITIONS_CONFIG['QUIET_PERIOD_ENABLED']
    quiet_period_seconds = SELL_CONDITIONS_CONFIG['QUIET_PERIOD_SECONDS']
    quiet_period_min_amount = SELL_CONDITIONS_CONFIG['QUIET_PERIOD_MIN_AMOUNT']
    
    # 获取买入前N笔交易的最小价格
    min_price_before_buy = get_min_price_before_buy(trade_data, buy_index, lookback_count)
    
    retracement_count = 0  # 回撤条件连续满足计数器
    
    for i in range(buy_index, len(trade_data)):
        trade = trade_data[i]
        current_price = trade['price']
        current_time = trade['tradetime']
        current_nowsol = float(trade.get('nowsol', 0))
        current_tradeamount = float(trade.get('tradeamount', 0))
        
        # 更新最高价格和最大盈利率
        if current_price > max_price:
            max_price = current_price
            max_profit_rate = (max_price - original_buy_price) / original_buy_price
        
        # 计算当前盈利率
        current_profit_rate = (current_price - original_buy_price) / original_buy_price
        
        # 条件1: 当市值 >= X SOL 时直接卖出
        if current_nowsol >= max_nowsol_sell:
            return i, f"市值止盈 (nowsol={current_nowsol:.2f} >= {max_nowsol_sell})"
        
        # 条件2: 当亏损达到X%，且当前价格小于买入前7笔交易的最小价格时，直接卖出
        if current_profit_rate <= -loss_percentage:
            if min_price_before_buy is not None and current_price < min_price_before_buy:
                return i, f"亏损止损 (亏损{abs(current_profit_rate)*100:.2f}%, 价格{current_price:.8f} < 前{lookback_count}单最低{min_price_before_buy:.8f})"
        
        # 条件3和4: 回撤止损
        if max_price > original_buy_price:
            # 计算从最高点的回撤比例
            retracement = (max_price - current_price) / max_price
            
            if max_profit_rate < high_profit_threshold:
                # 条件3: 最大盈利 < 50% 时，回撤达到 X% 且连续满足 N 次卖出
                if retracement >= retracement_low:
                    retracement_count += 1
                    if retracement_count >= retracement_min_count:
                        return i, f"回撤止损 (最大盈利{max_profit_rate*100:.2f}%<{high_profit_threshold*100:.0f}%, 回撤{retracement*100:.2f}%>={retracement_low*100:.0f}%, 连续{retracement_count}次)"
                else:
                    retracement_count = 0
            else:
                # 条件4: 最大盈利 >= 50% 时，回撤达到 X% 且连续满足 N 次卖出
                if retracement >= retracement_high:
                    retracement_count += 1
                    if retracement_count >= retracement_min_count:
                        return i, f"回撤止损 (最大盈利{max_profit_rate*100:.2f}%>={high_profit_threshold*100:.0f}%, 回撤{retracement*100:.2f}%>={retracement_high*100:.0f}%, 连续{retracement_count}次)"
                else:
                    retracement_count = 0
        
        # 条件5: 时间止损 - 持有超过最大持有时间
        hold_time_seconds = (current_time - buy_time) / 1000
        if hold_time_seconds > max_hold_seconds:
            if i > buy_index:
                return i - 1, f"时间止损 (持有{hold_time_seconds:.1f}秒)"
            else:
                return i, f"时间止损 (持有{hold_time_seconds:.1f}秒，价格一致)"
        
        # 条件6: 冷淡期卖出 - 近N秒内没有超过X金额的交易，遇到卖单就卖出
        if quiet_period_enabled and current_tradeamount < 0:  # 当前是卖单
            # 检查近N秒内是否有超过X金额的交易
            quiet_period_start_time = current_time - quiet_period_seconds * 1000  # 毫秒
            has_large_trade = False
            
            # 向前遍历检查时间窗口内的交易
            for j in range(i - 1, buy_index - 1, -1):
                prev_trade = trade_data[j]
                prev_time = prev_trade['tradetime']
                
                # 如果超出时间窗口，停止检查
                if prev_time < quiet_period_start_time:
                    break
                
                # 检查是否有超过阈值的交易
                prev_amount = abs(float(prev_trade.get('tradeamount', 0)))
                if prev_amount >= quiet_period_min_amount:
                    has_large_trade = True
                    break
            
            # 如果近N秒内没有大额交易，卖出
            if not has_large_trade:
                return i, f"冷淡期卖出 (近{quiet_period_seconds}秒内无>{quiet_period_min_amount}SOL交易)"
    
    # 如果到最后都没有卖出，强制卖出
    return len(trade_data) - 1, "强制卖出 (到达交易数据末尾)"


# monkey patch
pump.find_buy_signal = variant_find_buy_signal
pump.find_sell_signal = variant_find_sell_signal

# 保存原始的 backtest_mint 函数
original_backtest_mint = pump.backtest_mint

def wrapped_backtest_mint(mint_name: str, mint_data: Dict) -> List[Dict]:
    """包装的回测函数，用于收集debug统计数据"""
    trades = original_backtest_mint(mint_name, mint_data)
    
    # 如果是debug模式，记录每笔交易的结果
    has_debug_mode = (BUY_CONDITIONS_CONFIG['TIME_DIFF_CHECK_MODE'] == 'debug' or 
                      BUY_CONDITIONS_CONFIG['MAX_AMOUNT_CHECK_MODE'] == 'debug' or 
                      BUY_CONDITIONS_CONFIG['PRICE_VOLATILITY_CHECK_MODE'] == 'debug' or
                      BUY_CONDITIONS_CONFIG['TIME_VOLATILITY_CHECK_MODE'] == 'debug' or
                      BUY_CONDITIONS_CONFIG['AMOUNT_VOLATILITY_CHECK_MODE'] == 'debug' or
                      BUY_CONDITIONS_CONFIG['PRICE_RATIO_CHECK_MODE'] == 'debug' or
                      BUY_CONDITIONS_CONFIG['BUY_COUNT_CHECK_MODE'] == 'debug' or
                      BUY_CONDITIONS_CONFIG['SELL_COUNT_CHECK_MODE'] == 'debug' or
                      BUY_CONDITIONS_CONFIG['LARGE_TRADE_RATIO_CHECK_MODE'] == 'debug' or
                      BUY_CONDITIONS_CONFIG['SMALL_TRADE_RATIO_CHECK_MODE'] == 'debug' or
                      BUY_CONDITIONS_CONFIG['CONSECUTIVE_BUY_CHECK_MODE'] == 'debug' or
                      BUY_CONDITIONS_CONFIG['CONSECUTIVE_SELL_CHECK_MODE'] == 'debug')
    
    if has_debug_mode:
        for trade in trades:
            is_profitable = trade.get('is_profitable', False)
            
            # 从当前信号的debug信息中获取数据
            # 注意：由于每次调用 find_buy_signal 都会更新 current_signal_info，
            # 这里需要重新计算这些值
            trade_data = mint_data['trade_data']
            buy_trigger_index = trade.get('buy_trigger_index', 0)
            
            # 重新计算时间差
            time_diff = None
            if BUY_CONDITIONS_CONFIG['TIME_DIFF_CHECK_MODE'] == 'debug' and buy_trigger_index > 0:
                try:
                    current_time = int(trade_data[buy_trigger_index].get('tradetime', 0))
                    prev_time = int(trade_data[buy_trigger_index - 1].get('tradetime', 0))
                    time_diff = current_time - prev_time
                    # 记录到所有交易的时间差列表
                    debug_stats.record_time_diff_check(time_diff)
                except (TypeError, ValueError):
                    pass
            
            # 重新计算 is_max_amount
            is_max_amount = None
            if BUY_CONDITIONS_CONFIG['MAX_AMOUNT_CHECK_MODE'] == 'debug':
                abs_amount = abs(float(trade_data[buy_trigger_index].get('tradeamount', 0)))
                max_amount_threshold = BUY_CONDITIONS_CONFIG['MAX_AMOUNT_MIN_THRESHOLD']
                max_amount_lookback = BUY_CONDITIONS_CONFIG['MAX_AMOUNT_LOOKBACK_COUNT']
                is_max_amount = is_max_amount_in_recent_trades(trade_data, buy_trigger_index, abs_amount, max_amount_threshold, max_amount_lookback)
                # 记录到统计数据
                debug_stats.record_max_amount_check(is_max_amount)
            
            # 重新计算波动率
            price_volatility = None
            time_volatility = None
            amount_volatility = None
            need_volatility = (BUY_CONDITIONS_CONFIG['PRICE_VOLATILITY_CHECK_MODE'] == 'debug' or
                              BUY_CONDITIONS_CONFIG['TIME_VOLATILITY_CHECK_MODE'] == 'debug' or
                              BUY_CONDITIONS_CONFIG['AMOUNT_VOLATILITY_CHECK_MODE'] == 'debug')
            if need_volatility:
                volatility_lookback = BUY_CONDITIONS_CONFIG['VOLATILITY_LOOKBACK_COUNT']
                volatility_min_amount = BUY_CONDITIONS_CONFIG['VOLATILITY_MIN_AMOUNT']
                price_volatility, time_volatility, amount_volatility = get_recent_trades_volatility(trade_data, buy_trigger_index, volatility_lookback, volatility_min_amount, 'all')
                
                # 记录波动率统计
                if BUY_CONDITIONS_CONFIG['PRICE_VOLATILITY_CHECK_MODE'] == 'debug' and price_volatility is not None:
                    debug_stats.volatility_stats['price_volatility_values'].append(price_volatility)
                if BUY_CONDITIONS_CONFIG['TIME_VOLATILITY_CHECK_MODE'] == 'debug' and time_volatility is not None:
                    debug_stats.volatility_stats['time_volatility_values'].append(time_volatility)
                if BUY_CONDITIONS_CONFIG['AMOUNT_VOLATILITY_CHECK_MODE'] == 'debug' and amount_volatility is not None:
                    debug_stats.volatility_stats['amount_volatility_values'].append(amount_volatility)
                debug_stats.volatility_stats['total'] += 1
            
            # 重新计算价格比例
            price_ratio = None
            if BUY_CONDITIONS_CONFIG['PRICE_RATIO_CHECK_MODE'] == 'debug':
                try:
                    current_price = float(trade_data[buy_trigger_index].get('price', 0))
                    if current_price > 0:
                        price_ratio_lookback = BUY_CONDITIONS_CONFIG['PRICE_RATIO_LOOKBACK_COUNT']
                        price_ratio = get_price_ratio_to_min(trade_data, buy_trigger_index, current_price, price_ratio_lookback)
                        # 不管是否为None，都记录（None表示数据不足）
                        if price_ratio is not None:
                            debug_stats.record_price_ratio_check(price_ratio)
                except (TypeError, ValueError):
                    pass
            
            # 重新计算买卖单数量
            buy_count = None
            sell_count = None
            if BUY_CONDITIONS_CONFIG['BUY_COUNT_CHECK_MODE'] == 'debug' or BUY_CONDITIONS_CONFIG['SELL_COUNT_CHECK_MODE'] == 'debug':
                buy_count_lookback = BUY_CONDITIONS_CONFIG['BUY_COUNT_LOOKBACK_COUNT']
                sell_count_lookback = BUY_CONDITIONS_CONFIG['SELL_COUNT_LOOKBACK_COUNT']
                # 分别获取买卖单数量
                buy_count, _ = get_buy_sell_count(trade_data, buy_trigger_index, buy_count_lookback)
                _, sell_count = get_buy_sell_count(trade_data, buy_trigger_index, sell_count_lookback)
                
                if BUY_CONDITIONS_CONFIG['BUY_COUNT_CHECK_MODE'] == 'debug':
                    debug_stats.record_buy_count_check(buy_count)
                if BUY_CONDITIONS_CONFIG['SELL_COUNT_CHECK_MODE'] == 'debug':
                    debug_stats.record_sell_count_check(sell_count)
            
            # 重新计算大小单占比
            large_trade_ratio = None
            small_trade_ratio = None
            if BUY_CONDITIONS_CONFIG['LARGE_TRADE_RATIO_CHECK_MODE'] == 'debug' or BUY_CONDITIONS_CONFIG['SMALL_TRADE_RATIO_CHECK_MODE'] == 'debug':
                large_lookback = BUY_CONDITIONS_CONFIG['LARGE_TRADE_RATIO_LOOKBACK']
                small_lookback = BUY_CONDITIONS_CONFIG['SMALL_TRADE_RATIO_LOOKBACK']
                large_threshold = BUY_CONDITIONS_CONFIG['LARGE_TRADE_THRESHOLD']
                small_threshold = BUY_CONDITIONS_CONFIG['SMALL_TRADE_THRESHOLD']
                max_lookback = max(large_lookback, small_lookback)
                large_trade_ratio, small_trade_ratio = get_large_small_trade_ratio(trade_data, buy_trigger_index, max_lookback, large_threshold, small_threshold)
                
                if BUY_CONDITIONS_CONFIG['LARGE_TRADE_RATIO_CHECK_MODE'] == 'debug':
                    debug_stats.record_large_trade_ratio_check(large_trade_ratio)
                if BUY_CONDITIONS_CONFIG['SMALL_TRADE_RATIO_CHECK_MODE'] == 'debug':
                    debug_stats.record_small_trade_ratio_check(small_trade_ratio)
            
            # 重新计算连续买卖单数量
            consecutive_buy = None
            consecutive_sell = None
            if BUY_CONDITIONS_CONFIG['CONSECUTIVE_BUY_CHECK_MODE'] == 'debug' or BUY_CONDITIONS_CONFIG['CONSECUTIVE_SELL_CHECK_MODE'] == 'debug':
                buy_threshold = BUY_CONDITIONS_CONFIG['CONSECUTIVE_BUY_THRESHOLD']
                sell_threshold = BUY_CONDITIONS_CONFIG['CONSECUTIVE_SELL_THRESHOLD']
                consecutive_buy, consecutive_sell = get_consecutive_buy_sell_count(trade_data, buy_trigger_index, buy_threshold, sell_threshold)
                
                if BUY_CONDITIONS_CONFIG['CONSECUTIVE_BUY_CHECK_MODE'] == 'debug':
                    debug_stats.record_consecutive_buy_check(consecutive_buy)
                if BUY_CONDITIONS_CONFIG['CONSECUTIVE_SELL_CHECK_MODE'] == 'debug':
                    debug_stats.record_consecutive_sell_check(consecutive_sell)
            
            # 记录交易结果
            profit_rate = trade.get('profit_rate', 0.0)
            debug_stats.record_trade_result(is_profitable, time_diff, is_max_amount, price_volatility, time_volatility, amount_volatility, price_ratio, buy_count, sell_count, large_trade_ratio, small_trade_ratio, consecutive_buy, consecutive_sell, profit_rate)
    
    return trades

# 替换 backtest_mint 函数
pump.backtest_mint = wrapped_backtest_mint

start = time.time()
print('=' * 60)
print('基本条件组合回测')
print('=' * 60)
print(f"买入条件配置:")
print(f"  1. 距离创币时间 >= {BUY_CONDITIONS_CONFIG['TIME_FROM_CREATION_MINUTES']} 分钟")
print(f"  2. 市值范围(nowsol): {BUY_CONDITIONS_CONFIG['NOWSOL_RANGE']}")
print(f"  3. 交易金额范围: {BUY_CONDITIONS_CONFIG['TRADE_AMOUNT_RANGE']}")
mode_desc = {'off': '禁用', 'online': '启用', 'debug': '调试'}
print(f"  4. 距上笔交易时间差: {mode_desc.get(BUY_CONDITIONS_CONFIG['TIME_DIFF_CHECK_MODE'], BUY_CONDITIONS_CONFIG['TIME_DIFF_CHECK_MODE'])}")
if BUY_CONDITIONS_CONFIG['TIME_DIFF_CHECK_MODE'] == 'online':
    print(f"     时间差范围: {BUY_CONDITIONS_CONFIG['TIME_DIFF_FROM_LAST_TRADE_RANGE']} 毫秒")
print(f"  5. 过滤后前{BUY_CONDITIONS_CONFIG['FILTERED_TRADES_COUNT']}笔交易总和范围: {BUY_CONDITIONS_CONFIG['FILTERED_TRADES_SUM_RANGE']}")
print(f"     (过滤金额阈值: {BUY_CONDITIONS_CONFIG['FILTERED_TRADES_MIN_AMOUNT']})")
trade_type_desc = {'buy': '买入', 'sell': '卖出', 'both': '买入/卖出'}
print(f"  6. 交易类型: {trade_type_desc.get(BUY_CONDITIONS_CONFIG['TRADE_TYPE'], BUY_CONDITIONS_CONFIG['TRADE_TYPE'])}")
mode_desc = {'off': '禁用', 'online': '启用', 'debug': '调试'}
print(f"  7. 当前交易金额是否为近{BUY_CONDITIONS_CONFIG['MAX_AMOUNT_LOOKBACK_COUNT']}单中最大: {mode_desc.get(BUY_CONDITIONS_CONFIG['MAX_AMOUNT_CHECK_MODE'], BUY_CONDITIONS_CONFIG['MAX_AMOUNT_CHECK_MODE'])}")
print(f"  8. 近{BUY_CONDITIONS_CONFIG['VOLATILITY_LOOKBACK_COUNT']}单波动率检查:")
print(f"     8a. 价格波动率: {mode_desc.get(BUY_CONDITIONS_CONFIG['PRICE_VOLATILITY_CHECK_MODE'], BUY_CONDITIONS_CONFIG['PRICE_VOLATILITY_CHECK_MODE'])}")
if BUY_CONDITIONS_CONFIG['PRICE_VOLATILITY_CHECK_MODE'] == 'online':
    print(f"         范围: {BUY_CONDITIONS_CONFIG['PRICE_VOLATILITY_RANGE']}")
print(f"     8b. 时间波动率: {mode_desc.get(BUY_CONDITIONS_CONFIG['TIME_VOLATILITY_CHECK_MODE'], BUY_CONDITIONS_CONFIG['TIME_VOLATILITY_CHECK_MODE'])}")
if BUY_CONDITIONS_CONFIG['TIME_VOLATILITY_CHECK_MODE'] == 'online':
    print(f"         范围: {BUY_CONDITIONS_CONFIG['TIME_VOLATILITY_RANGE']}")
print(f"     8c. 金额波动率: {mode_desc.get(BUY_CONDITIONS_CONFIG['AMOUNT_VOLATILITY_CHECK_MODE'], BUY_CONDITIONS_CONFIG['AMOUNT_VOLATILITY_CHECK_MODE'])}")
if BUY_CONDITIONS_CONFIG['AMOUNT_VOLATILITY_CHECK_MODE'] == 'online':
    print(f"         范围: {BUY_CONDITIONS_CONFIG['AMOUNT_VOLATILITY_RANGE']}")
print(f"  9. 价格比例检查 (当前价/近{BUY_CONDITIONS_CONFIG['PRICE_RATIO_LOOKBACK_COUNT']}单最低价): {mode_desc.get(BUY_CONDITIONS_CONFIG['PRICE_RATIO_CHECK_MODE'], BUY_CONDITIONS_CONFIG['PRICE_RATIO_CHECK_MODE'])}")
if BUY_CONDITIONS_CONFIG['PRICE_RATIO_CHECK_MODE'] == 'online':
    print(f"     涨幅范围: {BUY_CONDITIONS_CONFIG['PRICE_RATIO_RANGE']}%")
print(f"  10. 近{BUY_CONDITIONS_CONFIG['BUY_COUNT_LOOKBACK_COUNT']}单买单数量检查: {mode_desc.get(BUY_CONDITIONS_CONFIG['BUY_COUNT_CHECK_MODE'], BUY_CONDITIONS_CONFIG['BUY_COUNT_CHECK_MODE'])}")
if BUY_CONDITIONS_CONFIG['BUY_COUNT_CHECK_MODE'] == 'online':
    print(f"     最少买单数量: {BUY_CONDITIONS_CONFIG['BUY_COUNT_MIN']}")
print(f"  11. 近{BUY_CONDITIONS_CONFIG['SELL_COUNT_LOOKBACK_COUNT']}单卖单数量检查: {mode_desc.get(BUY_CONDITIONS_CONFIG['SELL_COUNT_CHECK_MODE'], BUY_CONDITIONS_CONFIG['SELL_COUNT_CHECK_MODE'])}")
if BUY_CONDITIONS_CONFIG['SELL_COUNT_CHECK_MODE'] == 'online':
    print(f"     最少卖单数量: {BUY_CONDITIONS_CONFIG['SELL_COUNT_MIN']}")
print(f"  12. 近{BUY_CONDITIONS_CONFIG['LARGE_TRADE_RATIO_LOOKBACK']}单大单占比检查: {mode_desc.get(BUY_CONDITIONS_CONFIG['LARGE_TRADE_RATIO_CHECK_MODE'], BUY_CONDITIONS_CONFIG['LARGE_TRADE_RATIO_CHECK_MODE'])}")
if BUY_CONDITIONS_CONFIG['LARGE_TRADE_RATIO_CHECK_MODE'] == 'online':
    print(f"     大单阈值: >={BUY_CONDITIONS_CONFIG['LARGE_TRADE_THRESHOLD']}SOL, 占比范围: {BUY_CONDITIONS_CONFIG['LARGE_TRADE_RATIO_RANGE']}")
print(f"  13. 近{BUY_CONDITIONS_CONFIG['SMALL_TRADE_RATIO_LOOKBACK']}单小单占比检查: {mode_desc.get(BUY_CONDITIONS_CONFIG['SMALL_TRADE_RATIO_CHECK_MODE'], BUY_CONDITIONS_CONFIG['SMALL_TRADE_RATIO_CHECK_MODE'])}")
if BUY_CONDITIONS_CONFIG['SMALL_TRADE_RATIO_CHECK_MODE'] == 'online':
    print(f"     小单阈值: <{BUY_CONDITIONS_CONFIG['SMALL_TRADE_THRESHOLD']}SOL, 占比范围: {BUY_CONDITIONS_CONFIG['SMALL_TRADE_RATIO_RANGE']}")
print(f"  14. 连续大额买单检查: {mode_desc.get(BUY_CONDITIONS_CONFIG['CONSECUTIVE_BUY_CHECK_MODE'], BUY_CONDITIONS_CONFIG['CONSECUTIVE_BUY_CHECK_MODE'])}")
if BUY_CONDITIONS_CONFIG['CONSECUTIVE_BUY_CHECK_MODE'] == 'online':
    print(f"     买单阈值: >={BUY_CONDITIONS_CONFIG['CONSECUTIVE_BUY_THRESHOLD']}SOL, 最少连续: {BUY_CONDITIONS_CONFIG['CONSECUTIVE_BUY_MIN']}")
print(f"  15. 连续大额卖单检查: {mode_desc.get(BUY_CONDITIONS_CONFIG['CONSECUTIVE_SELL_CHECK_MODE'], BUY_CONDITIONS_CONFIG['CONSECUTIVE_SELL_CHECK_MODE'])}")
if BUY_CONDITIONS_CONFIG['CONSECUTIVE_SELL_CHECK_MODE'] == 'online':
    print(f"     卖单阈值: >={BUY_CONDITIONS_CONFIG['CONSECUTIVE_SELL_THRESHOLD']}SOL, 最多连续: {BUY_CONDITIONS_CONFIG['CONSECUTIVE_SELL_MAX']}")
print(f"\n卖出条件配置:")
print(f"  1. 市值止盈: nowsol >= {SELL_CONDITIONS_CONFIG['MAX_NOWSOL_SELL']} SOL")
print(f"  2. 亏损止损: 亏损 >= {SELL_CONDITIONS_CONFIG['LOSS_PERCENTAGE']*100:.0f}% 且价格 < 前{SELL_CONDITIONS_CONFIG['LOOKBACK_TRADES_FOR_MIN_PRICE']}单最低价")
print(f"  3. 回撤止损(低盈利): 最大盈利 < {SELL_CONDITIONS_CONFIG['HIGH_PROFIT_THRESHOLD']*100:.0f}% 时，回撤 >= {SELL_CONDITIONS_CONFIG['RETRACEMENT_LOW_PROFIT']*100:.0f}%")
print(f"  4. 回撤止损(高盈利): 最大盈利 >= {SELL_CONDITIONS_CONFIG['HIGH_PROFIT_THRESHOLD']*100:.0f}% 时，回撤 >= {SELL_CONDITIONS_CONFIG['RETRACEMENT_HIGH_PROFIT']*100:.0f}%")
print(f"  5. 时间止损: 持有 > {SELL_CONDITIONS_CONFIG['MAX_HOLD_TIME_SECONDS']} 秒")
print(f"  6. 冷淡期卖出: 近{SELL_CONDITIONS_CONFIG['QUIET_PERIOD_SECONDS']}秒内无>{SELL_CONDITIONS_CONFIG['QUIET_PERIOD_MIN_AMOUNT']}SOL交易时遇卖单卖出 (启用: {SELL_CONDITIONS_CONFIG['QUIET_PERIOD_ENABLED']})")
print('=' * 60)


log_file = '/Users/xcold/Desktop/js_log_mint_0209.log'


pump.run_backtest(log_file)

# 如果有debug模式的统计数据，打印摘要
has_debug_mode = (BUY_CONDITIONS_CONFIG['TIME_DIFF_CHECK_MODE'] == 'debug' or 
                  BUY_CONDITIONS_CONFIG['MAX_AMOUNT_CHECK_MODE'] == 'debug' or 
                  BUY_CONDITIONS_CONFIG['PRICE_VOLATILITY_CHECK_MODE'] == 'debug' or
                  BUY_CONDITIONS_CONFIG['TIME_VOLATILITY_CHECK_MODE'] == 'debug' or
                  BUY_CONDITIONS_CONFIG['AMOUNT_VOLATILITY_CHECK_MODE'] == 'debug' or
                  BUY_CONDITIONS_CONFIG['PRICE_RATIO_CHECK_MODE'] == 'debug' or
                  BUY_CONDITIONS_CONFIG['BUY_COUNT_CHECK_MODE'] == 'debug' or
                  BUY_CONDITIONS_CONFIG['SELL_COUNT_CHECK_MODE'] == 'debug' or
                  BUY_CONDITIONS_CONFIG['LARGE_TRADE_RATIO_CHECK_MODE'] == 'debug' or
                  BUY_CONDITIONS_CONFIG['SMALL_TRADE_RATIO_CHECK_MODE'] == 'debug' or
                  BUY_CONDITIONS_CONFIG['CONSECUTIVE_BUY_CHECK_MODE'] == 'debug' or
                  BUY_CONDITIONS_CONFIG['CONSECUTIVE_SELL_CHECK_MODE'] == 'debug')
if has_debug_mode:
    debug_stats.print_summary()

end = time.time()
print(f'\n回测耗时: {end - start:.2f} 秒')