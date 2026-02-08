#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Solana量化回测系统
实现基于交易数据的买入卖出策略回测
"""
import math
import json
import datetime
import sys
from typing import Dict, List, Optional, Tuple

# 策略参数配置
STRATEGY_CONFIG = {
    # 买入策略参数
    'BUY_SIGNAL_AMOUNT': 0.4,  # 买单金额阈值
    'WINDOW_SIZE_7': 8,  # 7个交易窗口
    'WINDOW_SIZE_8': 8,  # 8个交易窗口
    'WINDOW_SIZE_19': 8,  # 19个交易窗口
    'MIN_SELL_COUNT': 5,  # 8个窗口中最少卖单数量
    'PRICE_INCREASE_THRESHOLD': 0.05,  # 价格上涨阈值(15%)
    'MIN_NET_SOL': -8,  # 19个交易窗口最少净SOL
    'MIN_NET_SOL_7':  -1.5,  # 7个交易窗口最大净SOL
    'MIN_NOW_SOL': 14,  # 买入点nowsol最小值
    'MIN_TIME_FROM_CREATION': 60 * 5,  # 距离创币最少时间(240秒=4分钟)
    'BUY_DELAY_MS': 200,  # 买入延迟(毫秒)
    
    # 卖出策略参数
    'STOP_LOSS_PERCENTAGE': 0.02,  # 止损百分比(10%)
    'TAKE_PROFIT_PERCENTAGE': 2.50,  # 止盈百分比(50%)
    'MAX_HOLD_TIME_SECONDS': 500,  # 最大持有时间(秒)
    'SELL_DELAY_MS': 200,  # 卖出延迟(毫秒)
    
    # 交易参数
    'BUY_AMOUNT_SOL': 0.1,  # 每次买入SOL数量   
    'TRANSACTION_FEE_RATE': 0.0125,  # 交易手续费率(1%)
    'FIXED_FEE': 0.0001,  # 固定手续费
    
    # 数据过滤参数
    'MIN_PRICE': 0.002,  # 最小价格阈值
}

# 目标用户统计
TARGET_USER = 'DaBPm5gSQJzkNiEnZQXkZ9dtr9df3UFWv7KGjUM5L32Y'
target_user_count = 0  # 全局计数器


def timestamp_to_datetime(timestamp_ms: int) -> str:
    """将时间戳转换为可读日期时间格式"""
    return datetime.datetime.fromtimestamp(timestamp_ms / 1000).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]


def load_mint_info(file_path: str = '/Users/xcold/Desktop/mint_temp.log') -> Dict:
    """加载mint交易信息"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"错误: 找不到文件 {file_path}")
        return {}
    except json.JSONDecodeError:
        print(f"错误: 无法解析JSON文件 {file_path}")
        return {}


def filter_valid_trades(trade_data: List[Dict]) -> List[Dict]:
    """过滤有效的交易数据"""
    valid_trades = []
    for trade in trade_data:
        price = trade.get('price', 0)
        if price is None or price == 0 or price > STRATEGY_CONFIG['MIN_PRICE']:
            continue
        if abs(trade.get('tradeamount', 0)) <= 0.3:
            continue
        if trade.get('tradetime', 0) <= 17571515717.43:
            continue
        valid_trades.append(trade)
    return valid_trades


def get_price_at_time(trade_data: List[Dict], target_time: int, current_index: int) -> Tuple[float, int]:
    """获取指定时间的价格，如果没有交易则返回触发点价格"""
    for i in range(current_index + 1, len(trade_data)):
        if trade_data[i]['tradetime'] >= target_time:
            # 返回目标时间前一个交易的价格
            if i > 0:
                return trade_data[i-1]['price'], i-1
            else:
                return trade_data[current_index]['price'], current_index
    
    # 如果没有找到，返回当前交易价格
    return trade_data[current_index]['price'], current_index


def find_buy_signal(trade_data: List[Dict], start_index: int, creation_time: int) -> Optional[int]:
    """寻找买入信号
    
    买入策略：
    1. 当前交易点交易大于0.5
    2. 买入点的nowsol要大于10
    3. 前8个交易窗口中小于0的卖单大于4个
    4. 8个交易窗口中最高价格比最低价格高15%
    5. 前19个交易窗口的买卖sol和需要大于-10
    6. 前7个交易窗口买卖sol和要小于-2.5
    7. 当前离创币时间大于2分钟
    """
    # 检查是否有足够的历史交易数据
    if start_index < STRATEGY_CONFIG['WINDOW_SIZE_19']:
        return None
    
    # 检查当前交易是否为大于0.5的买单
    current_trade = trade_data[start_index]
    if current_trade['tradeamount'] <= STRATEGY_CONFIG['BUY_SIGNAL_AMOUNT']:
        return None
    if current_trade['tradeamount'] >= 2:
        return None
    
    # 检查买入点的nowsol是否大于10
    current_nowsol = current_trade.get('nowsol', 100)
    if current_nowsol >= STRATEGY_CONFIG['MIN_NOW_SOL']:
        return None
    
    if current_nowsol <= 2.0:
        return None
    
    # 检查距离创币时间是否大于2分钟
    current_time = current_trade['tradetime']
    if (current_time - creation_time) / 1000 < STRATEGY_CONFIG['MIN_TIME_FROM_CREATION']:
        return None
    
    # 获取前7个交易窗口
    window_7_start = start_index - STRATEGY_CONFIG['WINDOW_SIZE_7']
    window_7_trades = trade_data[window_7_start:start_index]
    
    # 计算7个窗口的净SOL交易量
    net_sol_7 = sum(trade['tradeamount'] for trade in window_7_trades)
    if net_sol_7 >= STRATEGY_CONFIG['MIN_NET_SOL_7']:
        return None
    
    # 获取前8个交易窗口
    window_8_start = start_index - STRATEGY_CONFIG['WINDOW_SIZE_8']
    window_8_trades = trade_data[window_8_start:start_index]
    
    # 检查8个窗口中小于0的卖单数量
    sell_count = sum(1 for trade in window_8_trades if trade['tradeamount'] < 0)
    if sell_count <= STRATEGY_CONFIG['MIN_SELL_COUNT']:
        return None
    
    # 获取前19个交易窗口
    window_19_start = start_index - STRATEGY_CONFIG['WINDOW_SIZE_19']
    window_19_trades = trade_data[window_19_start:start_index]
    
    # 计算19个窗口的净SOL交易量
    net_sol = sum(trade['tradeamount'] for trade in window_19_trades)
    if net_sol <= STRATEGY_CONFIG['MIN_NET_SOL']:
        return None
    
    # 检查个窗口中价格变化
    prices_8 = [trade['price'] for trade in window_19_trades]
    max_price_8 = max(prices_8)
    min_price_8 = min(prices_8)
    
    if min_price_8 > (1 - STRATEGY_CONFIG['PRICE_INCREASE_THRESHOLD']) * max_price_8:
        return None

    # 检查当前交易后的5个买单中是否包含目标用户
    global target_user_count
    buy_count = 0
    found_target = False
    
    for j in range(start_index + 1, len(trade_data)):
        if buy_count >= 5:
            break
        if trade_data[j]['tradeamount'] > 0:  # 买单
            buy_count += 1
            if trade_data[j].get('user') == TARGET_USER:
                found_target = True
                break
    
    if found_target:
        target_user_count += 1
        return None
    
    return start_index


def find_sell_signal(trade_data: List[Dict], buy_index: int, buy_price: float, buy_time: int) -> Tuple[int, str]:
    """寻找卖出信号
    
    卖出策略：
    1. 如果当前价格低于买入价格5%则卖出
    2. 如果当前价格大于买入价格，更新买入价格为当前价格
    3. 如果实际盈利达到50%则卖出
    4. 如果当前交易时间大于买入120秒，则在上一个交易点触发卖出
    5. 如果当前交易离上一个交易间隔超过50秒，则在上一个交易点卖出
    6. 如果遍历到最后还没有卖出，则强制卖出
    """
    current_buy_price = buy_price  # 动态买入价格（会随价格上涨而更新）
    original_buy_price = buy_price  # 原始买入价格，用于计算盈利率
    
    for i in range(buy_index, len(trade_data)):
        trade = trade_data[i]
        current_price = trade['price']
        current_time = trade['tradetime']
        
        # 如果当前价格大于买入价格，更新买入价格
        if current_price > current_buy_price:
            current_buy_price = current_price
        
        # 止损检查 - 价格低于当前买入价格5%
        if current_price < current_buy_price * (1 - STRATEGY_CONFIG['STOP_LOSS_PERCENTAGE']):
            return i, f"止损卖出 (价格从{current_buy_price:.8f}跌至{current_price:.8f})"
        
        # 止盈检查 - 相对于原始买入价格盈利超过50%
        profit_rate = (current_price - original_buy_price) / original_buy_price
        if profit_rate > STRATEGY_CONFIG['TAKE_PROFIT_PERCENTAGE']:
            return i, f"止盈卖出 (盈利{profit_rate*100:.2f}%)"
        
        # 时间止损检查 - 持有超过120秒
        if (current_time - buy_time) / 1000 > STRATEGY_CONFIG['MAX_HOLD_TIME_SECONDS']:
            if i > buy_index:
                return i-1, f"时间止损 (持有{(current_time - buy_time)/1000:.1f}秒)"
            else:
                # 如果上一个点就是买入点，则卖出价格和买入价格一致
                return i, f"时间止损 (持有{(current_time - buy_time)/1000:.1f}秒，价格一致)"
    
    # 如果到最后都没有卖出，强制卖出
    return len(trade_data) - 1, "强制卖出 (到达交易数据末尾)"


def calculate_transaction_fee(amount: float) -> float:
    """计算交易手续费"""
    return amount * STRATEGY_CONFIG['TRANSACTION_FEE_RATE'] + STRATEGY_CONFIG['FIXED_FEE']


def calc_buy_amount(now_sol: float) -> float:
    """计算动态买入金额"""
    a = 0.1085
    b = -0.0973
    return a * math.sqrt(now_sol) + b


def backtest_mint(mint_name: str, mint_data: Dict) -> List[Dict]:
    """对单个mint进行回测"""
    trade_data =mint_data['trade_data']# filter_valid_trades(mint_data['trade_data'])
    
    if len(trade_data) < 20:  # 交易数据太少（至少需要19个历史交易）
        return []
    
    trades = []
    last_sell_index = -1
    
    # 获取创币时间（第一个交易的时间）
    creation_time = trade_data[0]['tradetime']
    
    # 从第一个交易后开始寻找买入点（跳过创币人的初始买入）
    i = 1
    while i < len(trade_data):
        # 必须在上一个卖出点之后
        if i <= last_sell_index:
            i += 1
            continue
        
        # 寻找买入信号
        buy_signal_index = find_buy_signal(trade_data, i, creation_time)
        
        if buy_signal_index is not None:
            # 计算实际买入时间和价格
            buy_trigger_time = trade_data[buy_signal_index]['tradetime']
            actual_buy_time = buy_trigger_time + STRATEGY_CONFIG['BUY_DELAY_MS']
            buy_price, actual_buy_index = get_price_at_time(trade_data, actual_buy_time, buy_signal_index)
            
            # 寻找卖出信号
            sell_index, sell_reason = find_sell_signal(trade_data, actual_buy_index, buy_price, actual_buy_time)
            
            # 计算实际卖出时间和价格
            sell_trigger_time = trade_data[sell_index]['tradetime']
            actual_sell_time = sell_trigger_time + STRATEGY_CONFIG['SELL_DELAY_MS']
            sell_price, actual_sell_index = get_price_at_time(trade_data, actual_sell_time, sell_index)
            
            # 计算盈亏
            buy_amount_sol = calc_buy_amount(trade_data[actual_buy_index]['nowsol'])
            buy_amount_sol = max(buy_amount_sol, 0.205)
            buy_fee = calculate_transaction_fee(buy_amount_sol)
            
            # 实际买入的代币数量
            tokens_bought = (buy_amount_sol - buy_fee) / buy_price
            
            # 卖出获得的SOL
            sell_amount_sol = tokens_bought * sell_price
            sell_fee = calculate_transaction_fee(sell_amount_sol)
            final_sol = sell_amount_sol - sell_fee
            
            # 净盈亏
            profit = final_sol - buy_amount_sol
            profit_rate = profit / buy_amount_sol
            
            # 获取触发买入信号的交易快照
            buy_trigger_snapshot = trade_data[buy_signal_index]
            
            # 获取实际买入交易的快照
            actual_buy_snapshot = trade_data[actual_buy_index]
            
            # 获取触发卖出信号的交易快照
            sell_trigger_snapshot = trade_data[sell_index]
            
            # 获取实际卖出交易的快照
            actual_sell_snapshot = trade_data[actual_sell_index]
            
            trade_record = {
                'mint_name': mint_name,
                # 买入触发信息
                'buy_trigger_index': buy_signal_index,
                'buy_trigger_time': timestamp_to_datetime(buy_trigger_time),
                'buy_trigger_snapshot': buy_trigger_snapshot,
                # 实际买入信息
                'actual_buy_index': actual_buy_index,
                'actual_buy_time': timestamp_to_datetime(actual_buy_time),
                'actual_buy_snapshot': actual_buy_snapshot,
                'buy_price': buy_price,
                'buy_amount_sol': buy_amount_sol,
                'buy_fee': buy_fee,
                'tokens_bought': tokens_bought,
                # 卖出触发信息
                'sell_trigger_index': sell_index,
                'sell_trigger_time': timestamp_to_datetime(sell_trigger_time),
                'sell_trigger_snapshot': sell_trigger_snapshot,
                # 实际卖出信息
                'actual_sell_index': actual_sell_index,
                'actual_sell_time': timestamp_to_datetime(actual_sell_time),
                'actual_sell_snapshot': actual_sell_snapshot,
                'sell_price': sell_price,
                'sell_amount_sol': sell_amount_sol,
                'sell_fee': sell_fee,
                'sell_reason': sell_reason,
                # 盈亏信息
                'profit_sol': profit,
                'profit_rate': profit_rate,
                'is_profitable': profit > 0
            }
            
            trades.append(trade_record)
            last_sell_index = actual_sell_index
            i = actual_sell_index + 1
        else:
            i += 1
    
    return trades


def run_backtest(log_file_path: str = '/Users/xcold/Desktop/mint_temp.log'):
    """运行回测
    
    Args:
        log_file_path: mint交易信息日志文件路径，默认为 /Users/xcold/Desktop/mint_temp.log
    """
    print(f"开始加载mint信息，文件路径: {log_file_path}")
    mint_info = load_mint_info(log_file_path)
    
    if not mint_info:
        print("无法加载mint信息，程序退出")
        return
    
    print(f"加载了 {len(mint_info)} 个mint的数据")
    
    all_trades = []
    processed_count = 0
    
    print("开始回测...")
    for mint_name, mint_data in mint_info.items():
        try:
            mint_trades = backtest_mint(mint_name, mint_data)
            all_trades.extend(mint_trades)
            processed_count += 1
                
        except Exception as e:
            print(f"处理mint {mint_name} 时出错: {e}")
            continue
    
    # 计算统计信息
    total_trades = len(all_trades)
    if total_trades == 0:
        print("没有找到任何交易记录")
        return
    
    # 过滤掉盈利率大于100%的交易，用于最终盈利计算
    filtered_trades = [t for t in all_trades if t['profit_rate'] <= 2.0]  # 1.0 = 100%
    excluded_trades = [t for t in all_trades if t['profit_rate'] > 1.0]
    
    profitable_trades = [t for t in all_trades if t['is_profitable']]
    win_rate = len(profitable_trades) / total_trades
    
    # 使用过滤后的交易计算盈利统计
    total_profit = sum(t['profit_sol'] for t in filtered_trades)
    average_profit = total_profit / len(filtered_trades) if len(filtered_trades) > 0 else 0
    average_profit_rate = sum(t['profit_rate'] for t in filtered_trades) / len(filtered_trades) if len(filtered_trades) > 0 else 0
    
    # 输出统计信息
    print("\n" + "="*60)
    print("回测结果统计")
    print("="*60)
    print(f"总交易数: {total_trades}")
    print(f"盈利交易数: {len(profitable_trades)}")
    print(f"亏损交易数: {total_trades - len(profitable_trades)}")
    print(f"胜率: {win_rate:.2%}")
    print(f"排除高盈利(>100%)交易数: {len(excluded_trades)}")
    print(f"用于盈利计算的交易数: {len(filtered_trades)}")
    print(f"总盈利 (排除>100%): {total_profit:.6f} SOL")
    print(f"平均盈利 (排除>100%): {average_profit:.6f} SOL")
    print(f"平均盈利率 (排除>100%): {average_profit_rate:.2%}")
    print(f"\n目标用户 {TARGET_USER} 在信号后5个买单中出现次数: {target_user_count}")
    
    if len(excluded_trades) > 0:
        print(f"\n排除的高盈利交易:")
        print("-" * 40)
        for trade in excluded_trades:
            print(f"  {trade['mint_name']}: {trade['profit_rate']:.2%} ({trade['profit_sol']:.6f} SOL)")
    
    # 按盈利排序，展示前20个交易
    top_20_trades = all_trades[:1]
    
    print(f"\n前20个最佳交易:")
    print("=" * 80)
    for i, trade in enumerate(top_20_trades, 1):
        print(f"\n{i}. Mint: {trade['mint_name']}")
        print("-" * 80)
        
        # 买入信息
        print("【买入信息】")
        print(f"  触发买入:")
        buy_trigger = trade['buy_trigger_snapshot']
        print(f"    时间: {trade['buy_trigger_time']}")
        print(f"    价格: {buy_trigger.get('price', 'N/A'):.8f}")
        print(f"    交易量: {buy_trigger.get('tradeamount', 'N/A'):.6f}")
        print(f"    nowsol: {buy_trigger.get('nowsol', 'N/A'):.2f}")
        print(f"    用户: {buy_trigger.get('user', 'N/A')}")
        
        print(f"  实际买入:")
        actual_buy = trade['actual_buy_snapshot']
        print(f"    时间: {trade['actual_buy_time']}")
        print(f"    价格: {trade['buy_price']:.8f}")
        print(f"    交易量: {actual_buy.get('tradeamount', 'N/A'):.6f}")
        print(f"    nowsol: {actual_buy.get('nowsol', 'N/A'):.2f}")
        print(f"    用户: {actual_buy.get('user', 'N/A')}")
        print(f"    买入金额: {trade['buy_amount_sol']:.6f} SOL")
        print(f"    买入手续费: {trade['buy_fee']:.6f} SOL")
        print(f"    获得代币: {trade['tokens_bought']:.6f}")
        
        # 卖出信息
        print(f"\n  【卖出信息】")
        print(f"  触发卖出:")
        sell_trigger = trade['sell_trigger_snapshot']
        print(f"    时间: {trade['sell_trigger_time']}")
        print(f"    价格: {sell_trigger.get('price', 'N/A'):.8f}")
        print(f"    交易量: {sell_trigger.get('tradeamount', 'N/A'):.6f}")
        print(f"    用户: {sell_trigger.get('user', 'N/A')}")
        print(f"    卖出原因: {trade['sell_reason']}")
        
        print(f"  实际卖出:")
        actual_sell = trade['actual_sell_snapshot']
        print(f"    时间: {trade['actual_sell_time']}")
        print(f"    价格: {trade['sell_price']:.8f}")
        print(f"    交易量: {actual_sell.get('tradeamount', 'N/A'):.6f}")
        print(f"    用户: {actual_sell.get('user', 'N/A')}")
        print(f"    卖出金额: {trade['sell_amount_sol']:.6f} SOL")
        print(f"    卖出手续费: {trade['sell_fee']:.6f} SOL")
        
        # 盈亏信息
        print(f"\n  【盈亏信息】")
        print(f"    净盈利: {trade['profit_sol']:.6f} SOL")
        print(f"    盈利率: {trade['profit_rate']:.2%}")
        print(f"    是否盈利: {'✅ 是' if trade['is_profitable'] else '❌ 否'}")
        print("-" * 80)
    
    # 保存结果到JSON文件
    result_data = {
        'strategy_config': STRATEGY_CONFIG,
        'statistics': {
            'total_trades': total_trades,
            'profitable_trades': len(profitable_trades),
            'win_rate': win_rate,
            'excluded_high_profit_trades': len(excluded_trades),
            'filtered_trades_count': len(filtered_trades),
            'total_profit_sol': total_profit,  # 排除>100%后的总盈利
            'average_profit_sol': average_profit,  # 排除>100%后的平均盈利
            'average_profit_rate': average_profit_rate,  # 排除>100%后的平均盈利率
            'target_user_count': target_user_count,  # 目标用户出现次数
        },
        'excluded_trades': excluded_trades,  # 被排除的高盈利交易
        'all_trades': all_trades  # 所有交易记录
    }
    
    with open('result.json', 'w', encoding='utf-8') as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)
    
    print(f"所有交易数据已保存到 result.json")
    print(f"策略配置参数已包含在结果文件中")


if __name__ == "__main__":
    # 从命令行参数获取日志文件路径，否则使用默认路径
    log_file = '/Users/xcold/Desktop/mint_temp.log'
    
    if len(sys.argv) > 1:
        log_file = sys.argv[1]
    
    run_backtest(log_file)
