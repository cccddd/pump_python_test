---
name: pump回测框架
description:
  通过pump的日志文件，测试不同的买入条件和卖出条件，对最终盈利率、胜率的影响。
metadata:
  {
    "openclaw":
      {
        "emoji": "🛍️",
        "requires": {"bins": ["uv"]}
      }
  }
---

# Skill
通过提取每个交易单的行为特征，并将组合进行回测，得出高命中率/胜率/盈利率的组合。提供的回测文件./scripts/pump.py,你需要在scripts/rules目录下，创建一个组合策略的脚本文件（参考/Users/xcold/Desktop/pump-test/scripts/rule_demo.py代码内容）。要求提供出来胜率和盈利率和命中数提升到满足既定的目标：即命中数大于300，平均盈利率大于1%,胜率大于38%。

```样本日志 mint_temp.log
# 样本日志解释
{
    "7Xwb1pMCSpHv4y8ooqHezoP7YZJ2oxbENzc4U6o7pump": 
    {
    "creater": "GhKnmFMiUCadWZByDBEnvX1avSVcRiuCW3yFfSrXTpgT",//创币人
    "creatertime": 1769469250924,//创币时间
    "trade_data": [ //交易日志
      {
        "user": "D2J2P3x2qLKaCw1JC53jpLynxe45QNzMyAWZ7y7SLpB7",//交易用户
        "tradetime": 1769469250924,//交易时间，单位毫秒
        "tradeamount": 2.209444522857666,//交易金额，单位sol
        "nowsol": 5.855793476104736,//交易市值
        "price": 0.00003729430463503788//交易价格
      }
    ]
    }
}
```

## 修改触发买入条件，只需要更改 pump.find_buy_signal方法
```代码

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

```

## 修改触发卖出条件，只需要更改 pump.find_buy_signal方法
```代码


def variant_find_sell_signal(trade_data: List[Dict], buy_index: int, buy_price: float, buy_time: int) -> Tuple[int, str]:
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

# monkey patch
pump.find_sell_signal = variant_find_sell_signal

```
## 具体特征提取和条件组合逻辑。
我们可以采用漏斗方式(即先通过基本条件得到命中数和盈利数最高的策略，再逐一添加不同的特征条件，完成漏斗，比如先通过基本条件，筛选出来盈利的交易数高的【基本条件组合】，然后通过后续进一步特征提取，将高盈利数的【基本条件组合】里，通过逐一添加特征进行回测），最终将胜率和盈利率和命中数提升到满足既定的目标：即命中数大于300，平均盈利率大于1%,胜率大于38%。

首先基本条件目前我认为有3个，需要通过分桶训练，判断出来满足每个条件的值都有哪些
1、距离创币的时间：时间距离该mint的第一单交易（大部分是创币时间）的时间差大于T分钟，如T分组有(5)
2、当前市值：即newsol字段，在X范围里，如X分钟为((5,10),(5,15),(15,30))
3、当前交易单：当前触发的交易单是买/卖单，且交易金额的绝对值在Z范围，如Z分组有((0.5,1.0),(1.0,2.0))

进一步特征条件，你需要通过对量化交易的理解，对高频交易提取出各种特征，我可以给你举例几种维度，你需要扩展出来合适的特征。
1、当前交易距离上一次交易的时间差
2、过滤交易额绝对值小于A金额的交易单之后的B个交易单总和在C范围里，比如A的分组为(0.05,0.1),B的分组为(7,11),C的分组为((-5.0,-2.0),(-2.0,0))
3、过滤交易额绝对值小于A金额的交易单之后的B个交易单里，买单数量在C范围里，比如A的分组为(0.05,0.1),B的分组为(7,11),C的分组为((1,5))
4、当前交易，在xx单内完成底部反转
5、当前交易，在xx单内完成了高位突破
6、在xx个交易单里，交易的价格、交易的金额或者交易时间的均差大于xx
7、通过提取近60个交易单，通过klines形式，判断是否完成底部反转、高位突破、上涨趋势


## 数据实时汇报
1、每一次策略回测完，需要把【回测结果统计】返回给我，如果最后达到目标命中数大于300，平均盈利率大于1%,胜率大于38%，则需要强提醒下我


