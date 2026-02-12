use crate::{
    context::{
        context::{BuySnapshot, TradeContextNew, UnifyRecordContext},
        context_new::MintStatus,
        trader::TradeMessage,
    },
    help::{
        global::{GROUP_CACHE, MINT_CACHE2, UNIFY_BUY_CHANNEL, WATCH_CACHE},
        global_xd::xd_global_struct,
    },
    processer::PipelineHandler,
};
use async_trait::async_trait;
use serde::Deserialize;

// =============================================================================
// 买入条件配置
// =============================================================================

/// 条件检查模式
#[derive(Debug, Deserialize, Clone, PartialEq)]
pub enum CheckMode {
    Off,    // 禁用此条件
    Online, // 启用此条件，进行实际过滤
    Debug,  // 调试模式，只收集统计数据，不过滤
}

impl Default for CheckMode {
    fn default() -> Self {
        CheckMode::Off
    }
}

/// 交易类型过滤
#[derive(Debug, Deserialize, Clone, PartialEq)]
pub enum TradeTypeFilter {
    Buy,   // 只匹配买入交易 (tradeamount > 0)
    Sell,  // 只匹配卖出交易 (tradeamount < 0)
    Both,  // 匹配买入和卖出交易
}

impl Default for TradeTypeFilter {
    fn default() -> Self {
        TradeTypeFilter::Both
    }
}

#[derive(Debug, Deserialize, Clone)]
pub struct BuyConditionsConfig {
    // 条件1: 距离创币时间（分钟）
    pub time_from_creation_check_mode: CheckMode,
    pub time_from_creation_minutes: u64,
    pub time_from_creation_range: (f64, f64),
    
    // 条件2: 当前市值范围（nowsol字段）
    pub nowsol_check_mode: CheckMode,
    pub nowsol_range: (f32, f32),
    
    // 条件3: 当前交易单金额范围
    pub trade_amount_check_mode: CheckMode,
    pub trade_amount_range: (f32, f32),
    
    // 条件4: 当前交易单距离上一个交易单的时间差（毫秒）
    pub time_diff_check_mode: CheckMode,
    pub time_diff_from_last_trade_range: (u64, u64),
    
    // 条件5: 过滤后的前N笔交易总和范围
    pub filtered_trades_check_mode: CheckMode,
    pub filtered_trades_min_amount: f32,
    pub filtered_trades_count: usize,
    pub filtered_trades_sum_range: (f32, f32),
    
    // 条件6: 当前交易类型
    pub trade_type: TradeTypeFilter,
    
    // 条件7: 当前交易金额是否为近T单中最大
    pub max_amount_check_mode: CheckMode,
    pub max_amount_min_threshold: f32,
    pub max_amount_lookback_count: usize,
    
    // 条件8: 近N个交易单的波动率检查
    pub volatility_lookback_count: usize,
    pub volatility_min_amount: f32,
    
    // 条件8a: 价格波动率
    pub price_volatility_check_mode: CheckMode,
    pub price_volatility_range: (f64, f64),
    
    // 条件8b: 时间波动率
    pub time_volatility_check_mode: CheckMode,
    pub time_volatility_range: (f64, f64),
    
    // 条件8c: 金额波动率
    pub amount_volatility_check_mode: CheckMode,
    pub amount_volatility_range: (f64, f64),
    
    // 条件9: 当前交易价格/近N单最低价的比例
    pub price_ratio_check_mode: CheckMode,
    pub price_ratio_lookback_count: usize,
    pub price_ratio_range: (f64, f64),
    
    // 条件10: 近T个交易单里买单数量
    pub buy_count_check_mode: CheckMode,
    pub buy_count_lookback_count: usize,
    pub buy_count_min: usize,
    
    // 条件11: 近T个交易单里卖单数量
    pub sell_count_check_mode: CheckMode,
    pub sell_count_lookback_count: usize,
    pub sell_count_min: usize,
    
    // 条件12: 大单占比检查
    pub large_trade_ratio_check_mode: CheckMode,
    pub large_trade_ratio_lookback: usize,
    pub large_trade_threshold: f32,
    pub large_trade_ratio_range: (f64, f64),
    
    // 条件13: 小单占比检查
    pub small_trade_ratio_check_mode: CheckMode,
    pub small_trade_ratio_lookback: usize,
    pub small_trade_threshold: f32,
    pub small_trade_ratio_range: (f64, f64),
    
    // 条件14: 连续大额买单检查 (range模式)
    pub consecutive_buy_check_mode: CheckMode,
    pub consecutive_buy_threshold: f32,
    pub consecutive_buy_range: (i64, i64),
    
    // 条件15: 连续大额卖单检查 (range模式)
    pub consecutive_sell_check_mode: CheckMode,
    pub consecutive_sell_threshold: f32,
    pub consecutive_sell_range: (i64, i64),
    
    // 条件16: 近N秒内交易单数量
    pub recent_trade_count_check_mode: CheckMode,
    pub recent_trade_count_window_seconds: u64,
    pub recent_trade_count_range: (usize, usize),
    
    // 条件17: 近N单平均交易间隔时间
    pub avg_trade_interval_check_mode: CheckMode,
    pub avg_trade_interval_lookback_count: usize,
    pub avg_trade_interval_range: (u64, u64),

    // 条件18: 时间窗口内大额交易总和检查
    // 在指定毫秒窗口内，过滤金额绝对值>=阈值的交易，计算金额总和（买为正、卖为负）
    pub window_amount_sum_check_mode: CheckMode,
    pub window_amount_sum_window_ms: u64,
    pub window_amount_sum_min_amount: f32,
    pub window_amount_sum_range: (f64, f64),

    // 条件19: 时间窗口内大额交易买卖单数量检查
    // 在指定毫秒窗口内，过滤金额绝对值>=阈值的交易，分别统计买单和卖单数量
    pub window_buy_sell_count_check_mode: CheckMode,
    pub window_buy_sell_count_window_ms: u64,
    pub window_buy_sell_count_min_amount: f32,
    pub window_buy_sell_count_buy_range: (usize, usize),
    pub window_buy_sell_count_sell_range: (usize, usize),
}

impl Default for BuyConditionsConfig {
    fn default() -> Self {
        Self {
            // 条件1: 距离创币时间
            time_from_creation_check_mode: CheckMode::Debug,
            time_from_creation_minutes: 0,
            time_from_creation_range: (0.0, 100.0),
            
            // 条件2: 当前市值范围
            nowsol_check_mode: CheckMode::Debug,
            nowsol_range: (80.0, 250.0),
            
            // 条件3: 当前交易单金额范围
            trade_amount_check_mode: CheckMode::Debug,
            trade_amount_range: (4.5, 12.0),
            
            // 条件4: 时间差检查
            time_diff_check_mode: CheckMode::Online,
            time_diff_from_last_trade_range: (0, 800),
            
            // 条件5: 过滤后的前N笔交易总和范围
            filtered_trades_check_mode: CheckMode::Debug,
            filtered_trades_min_amount: 0.05,
            filtered_trades_count: 20,
            filtered_trades_sum_range: (-200.0, 150.0),
            
            // 条件6: 当前交易类型
            trade_type: TradeTypeFilter::Sell,
            
            // 条件7: 最大金额检查
            max_amount_check_mode: CheckMode::Debug,
            max_amount_min_threshold: 0.05,
            max_amount_lookback_count: 15,
            
            // 条件8: 波动率检查
            volatility_lookback_count: 15,
            volatility_min_amount: 0.1,
            
            // 条件8a: 价格波动率
            price_volatility_check_mode: CheckMode::Debug,
            price_volatility_range: (0.0, 1.0),
            
            // 条件8b: 时间波动率
            time_volatility_check_mode: CheckMode::Debug,
            time_volatility_range: (0.7, 5.0),
            
            // 条件8c: 金额波动率
            amount_volatility_check_mode: CheckMode::Debug,
            amount_volatility_range: (0.2, 1.0),
            
            // 条件9: 价格比例检查
            price_ratio_check_mode: CheckMode::Debug,
            price_ratio_lookback_count: 10,
            price_ratio_range: (0.0, 3.0),
            
            // 条件10: 买单数量检查
            buy_count_check_mode: CheckMode::Debug,
            buy_count_lookback_count: 30,
            buy_count_min: 15,
            
            // 条件11: 卖单数量检查
            sell_count_check_mode: CheckMode::Debug,
            sell_count_lookback_count: 25,
            sell_count_min: 3,
            
            // 条件12: 大单占比检查
            large_trade_ratio_check_mode: CheckMode::Debug,
            large_trade_ratio_lookback: 10,
            large_trade_threshold: 1.0,
            large_trade_ratio_range: (0.0, 0.3),
            
            // 条件13: 小单占比检查
            small_trade_ratio_check_mode: CheckMode::Online,
            small_trade_ratio_lookback: 30,
            small_trade_threshold: 0.4,
            small_trade_ratio_range: (0.2, 1.2),
            
            // 条件14: 连续大额买单检查 (range模式)
            consecutive_buy_check_mode: CheckMode::Debug,
            consecutive_buy_threshold: 1.0,
            consecutive_buy_range: (0, 2),
            
            // 条件15: 连续大额卖单检查 (range模式)
            consecutive_sell_check_mode: CheckMode::Debug,
            consecutive_sell_threshold: 0.1,
            consecutive_sell_range: (0, 2),
            
            // 条件16: 近N秒内交易单数量
            recent_trade_count_check_mode: CheckMode::Online,
            recent_trade_count_window_seconds: 1,
            recent_trade_count_range: (3, 600),
            
            // 条件17: 近N单平均交易间隔时间
            avg_trade_interval_check_mode: CheckMode::Online,
            avg_trade_interval_lookback_count: 15,
            avg_trade_interval_range: (0, 500),

            // 条件18: 时间窗口内大额交易总和检查
            window_amount_sum_check_mode: CheckMode::Online,
            window_amount_sum_window_ms: 600,
            window_amount_sum_min_amount: 0.0,
            window_amount_sum_range: (-5.0, 30.0),

            // 条件19: 时间窗口内大额交易买卖单数量检查
            window_buy_sell_count_check_mode: CheckMode::Online,
            window_buy_sell_count_window_ms: 30000,
            window_buy_sell_count_min_amount: 0.0,
            window_buy_sell_count_buy_range: (10, 100),
            window_buy_sell_count_sell_range: (0, 100),
        }
    }
}

// 全局买入条件配置
lazy_static::lazy_static! {
    pub static ref BUY_CONFIG: BuyConditionsConfig = BuyConditionsConfig::default();
}

// =============================================================================
// 买入条件检查函数
// =============================================================================

/// 检查买入条件（只有 Online 模式的条件才会真正过滤，Debug/Off 模式不影响买入）
/// 逻辑与 Python amm_quant_demo.py 中的 variant_find_buy_signal 完全一致
/// 返回 (是否满足所有Online条件, 拒绝原因)
pub fn check_buy_conditions(
    cfg: &BuyConditionsConfig,
    features: &BuyFeatures,
    data: &TradeContextNew,
    recent_trades: &[&crate::help::global_xd::PrepareTradeMetrics],
) -> (bool, String) {
    let mut reject_reason = String::new();
    
    // 条件1: 检查距离创币时间
    // Python: 无论什么模式都检查 time_from_creation_minutes 最小值
    let time_diff_minutes = features.time_from_creation_ms / 60000;
    if time_diff_minutes < cfg.time_from_creation_minutes as u128 {
        reject_reason = format!("创币时间不足({}min<{}min)", time_diff_minutes, cfg.time_from_creation_minutes);
        return (false, reject_reason);
    }
    // Online 模式额外检查范围
    if cfg.time_from_creation_check_mode == CheckMode::Online {
        let time_min_f = features.time_from_creation_min;
        let (cr_min, cr_max) = cfg.time_from_creation_range;
        if time_min_f < cr_min || time_min_f > cr_max {
            reject_reason = format!("创币时间不在范围({:.2}min不在[{:.2},{:.2}])", time_min_f, cr_min, cr_max);
            return (false, reject_reason);
        }
    }
    
    // 条件2: 检查市值范围
    // Python: 始终检查 nowsol_range（不受 check_mode 影响，Python 中无论 online/debug 都过滤）
    let (nowsol_min, nowsol_max) = cfg.nowsol_range;
    let current_nowsol = *data.post_sol_amount();
    if current_nowsol < nowsol_min || current_nowsol > nowsol_max {
        reject_reason = format!("市值不在范围({:.2}不在[{:.2},{:.2}])", current_nowsol, nowsol_min, nowsol_max);
        return (false, reject_reason);
    }
    
    // 条件3: 检查交易金额范围
    // Python: 始终检查 trade_amount_range
    let abs_amount = data.trade_sol_amount().abs();
    let (amount_min, amount_max) = cfg.trade_amount_range;
    if abs_amount < amount_min || abs_amount > amount_max {
        reject_reason = format!("交易金额不在范围({:.2}不在[{:.2},{:.2}])", abs_amount, amount_min, amount_max);
        return (false, reject_reason);
    }
    
    // 条件4: 检查时间差 (仅 Online 模式过滤)
    // Python: if time_diff_mode == 'online': 检查范围; debug/off: 不过滤
    if cfg.time_diff_check_mode == CheckMode::Online {
        let time_diff = features.time_diff_from_last_trade_ms;
        let (min_diff, max_diff) = cfg.time_diff_from_last_trade_range;
        if time_diff < min_diff as f64 || time_diff > max_diff as f64 {
            reject_reason = format!("时间差不在范围({:.0}ms不在[{},{}])", time_diff, min_diff, max_diff);
            return (false, reject_reason);
        }
    }
    
    // 条件5: 检查过滤后的前N笔交易总和
    // Python: 始终检查（有效交易数量不足返回None，总和不在范围返回None）
    let filtered_count = features.filtered_trades_count;
    if filtered_count < cfg.filtered_trades_count {
        reject_reason = format!("有效交易数量不足({}<{})", filtered_count, cfg.filtered_trades_count);
        return (false, reject_reason);
    }
    let filtered_sum = features.filtered_trades_sum as f32;
    let (sum_min, sum_max) = cfg.filtered_trades_sum_range;
    if filtered_sum < sum_min || filtered_sum > sum_max {
        reject_reason = format!("前{}笔交易总和不在范围({:.2}不在[{:.2},{:.2}])", 
            cfg.filtered_trades_count, filtered_sum, sum_min, sum_max);
        return (false, reject_reason);
    }
    
    // 条件6: 检查交易类型 (始终检查)
    // Python: 始终检查 trade_type
    let is_buy_trade = data.trade_type() == "buy";
    match cfg.trade_type {
        TradeTypeFilter::Buy => {
            if !is_buy_trade {
                reject_reason = "交易类型不是买入".to_string();
                return (false, reject_reason);
            }
        }
        TradeTypeFilter::Sell => {
            if is_buy_trade {
                reject_reason = "交易类型不是卖出".to_string();
                return (false, reject_reason);
            }
        }
        TradeTypeFilter::Both => {}
    }
    
    // 条件7: 检查是否为最大金额 (仅 Online 模式过滤)
    // Python: if max_amount_mode == 'online': 不是最大则返回None
    if cfg.max_amount_check_mode == CheckMode::Online {
        let mut filtered_amounts: Vec<f32> = Vec::new();
        for rt in recent_trades.iter().skip(1) {
            let amt = rt.buy_amount.abs();
            if amt >= cfg.max_amount_min_threshold {
                filtered_amounts.push(amt);
                if filtered_amounts.len() >= cfg.max_amount_lookback_count {
                    break;
                }
            }
        }
        if !filtered_amounts.is_empty() {
            let max_amt = filtered_amounts.iter().cloned().fold(f32::NEG_INFINITY, f32::max);
            if abs_amount <= max_amt {
                reject_reason = format!("不是近{}单中最大金额({:.2}<={:.2})", cfg.max_amount_lookback_count, abs_amount, max_amt);
                return (false, reject_reason);
            }
        }
    }
    
    // 条件8a: 价格波动率 (仅 Online 模式过滤)
    // Python: if price_volatility_mode == 'online': 检查范围，None也返回None
    if cfg.price_volatility_check_mode == CheckMode::Online {
        match features.price_volatility_cv {
            Some(pv) => {
                let (min_v, max_v) = cfg.price_volatility_range;
                if pv < min_v || pv > max_v {
                    reject_reason = format!("价格波动率不在范围({:.4}不在[{:.4},{:.4}])", pv, min_v, max_v);
                    return (false, reject_reason);
                }
            }
            None => {
                reject_reason = "价格波动率数据不足".to_string();
                return (false, reject_reason);
            }
        }
    }
    
    // 条件8b: 时间波动率 (仅 Online 模式过滤)
    if cfg.time_volatility_check_mode == CheckMode::Online {
        match features.time_volatility_cv {
            Some(tv) => {
                let (min_v, max_v) = cfg.time_volatility_range;
                if tv < min_v || tv > max_v {
                    reject_reason = format!("时间波动率不在范围({:.4}不在[{:.4},{:.4}])", tv, min_v, max_v);
                    return (false, reject_reason);
                }
            }
            None => {
                reject_reason = "时间波动率数据不足".to_string();
                return (false, reject_reason);
            }
        }
    }
    
    // 条件8c: 金额波动率 (仅 Online 模式过滤)
    if cfg.amount_volatility_check_mode == CheckMode::Online {
        match features.amount_volatility_cv {
            Some(av) => {
                let (min_v, max_v) = cfg.amount_volatility_range;
                if av < min_v || av > max_v {
                    reject_reason = format!("金额波动率不在范围({:.4}不在[{:.4},{:.4}])", av, min_v, max_v);
                    return (false, reject_reason);
                }
            }
            None => {
                reject_reason = "金额波动率数据不足".to_string();
                return (false, reject_reason);
            }
        }
    }
    
    // 条件9: 价格比例检查 (仅 Online 模式过滤)
    // Python: if price_ratio_mode == 'online': 检查范围
    if cfg.price_ratio_check_mode == CheckMode::Online {
        if let Some(ratio) = features.price_ratio {
            let (min_r, max_r) = cfg.price_ratio_range;
            if ratio < min_r || ratio > max_r {
                reject_reason = format!("价格比例不在范围({:.2}%不在[{:.2}%,{:.2}%])", ratio, min_r, max_r);
                return (false, reject_reason);
            }
        }
    }
    
    // 条件10: 买单数量检查 (仅 Online 模式过滤)
    // Python: if buy_count < buy_count_min: return None
    if cfg.buy_count_check_mode == CheckMode::Online {
        let buy_count = recent_trades.iter().skip(1)
            .take(cfg.buy_count_lookback_count)
            .filter(|rt| rt.trade_type == "buy")
            .count();
        if buy_count < cfg.buy_count_min {
            reject_reason = format!("买单数量不足({}<{})", buy_count, cfg.buy_count_min);
            return (false, reject_reason);
        }
    }
    
    // 条件11: 卖单数量检查 (仅 Online 模式过滤)
    // Python: if sell_count < sell_count_min: return None
    if cfg.sell_count_check_mode == CheckMode::Online {
        let sell_count = recent_trades.iter().skip(1)
            .take(cfg.sell_count_lookback_count)
            .filter(|rt| rt.trade_type != "buy")
            .count();
        if sell_count < cfg.sell_count_min {
            reject_reason = format!("卖单数量不足({}<{})", sell_count, cfg.sell_count_min);
            return (false, reject_reason);
        }
    }
    
    // 条件12: 大单占比检查 (仅 Online 模式过滤)
    // Python: large_trade_ratio = large_count / total_count; 检查是否在范围内
    // Python 使用 max(large_lookback, small_lookback) 作为实际 lookback（不含当前交易）
    if cfg.large_trade_ratio_check_mode == CheckMode::Online {
        let lookback = cfg.large_trade_ratio_lookback.max(cfg.small_trade_ratio_lookback).min(recent_trades.len().saturating_sub(1));
        if lookback > 0 {
            let large_count = recent_trades.iter().skip(1)
                .take(lookback)
                .filter(|rt| rt.buy_amount.abs() >= cfg.large_trade_threshold)
                .count();
            let large_ratio = large_count as f64 / lookback as f64;
            let (min_r, max_r) = cfg.large_trade_ratio_range;
            if large_ratio < min_r || large_ratio > max_r {
                reject_reason = format!("大单占比不在范围({:.2}不在[{:.2},{:.2}])", large_ratio, min_r, max_r);
                return (false, reject_reason);
            }
        }
    }
    
    // 条件13: 小单占比检查 (仅 Online 模式过滤)
    // Python: small_trade_ratio = small_count / total_count; 检查是否在范围内
    if cfg.small_trade_ratio_check_mode == CheckMode::Online {
        let lookback = cfg.large_trade_ratio_lookback.max(cfg.small_trade_ratio_lookback).min(recent_trades.len().saturating_sub(1));
        if lookback > 0 {
            let small_count = recent_trades.iter().skip(1)
                .take(lookback)
                .filter(|rt| rt.buy_amount.abs() < cfg.small_trade_threshold)
                .count();
            let small_ratio = small_count as f64 / lookback as f64;
            let (min_r, max_r) = cfg.small_trade_ratio_range;
            if small_ratio < min_r || small_ratio > max_r {
                reject_reason = format!("小单占比不在范围({:.2}不在[{:.2},{:.2}])", small_ratio, min_r, max_r);
                return (false, reject_reason);
            }
        }
    }
    
    // 条件14: 连续大额买单检查 (仅 Online 模式过滤, range模式)
    // Python: consecutive_buy_range = (cb_min, cb_max); if not (cb_min <= consecutive_buy <= cb_max): return None
    if cfg.consecutive_buy_check_mode == CheckMode::Online {
        let consecutive_buy = recent_trades.iter().skip(1)
            .take_while(|rt| rt.trade_type == "buy" && rt.buy_amount.abs() >= cfg.consecutive_buy_threshold)
            .count() as i64;
        let (min_c, max_c) = cfg.consecutive_buy_range;
        if consecutive_buy < min_c || consecutive_buy > max_c {
            reject_reason = format!("连续买单数量不在范围({}不在[{},{}])", consecutive_buy, min_c, max_c);
            return (false, reject_reason);
        }
    }
    
    // 条件15: 连续大额卖单检查 (仅 Online 模式过滤, range模式)
    // Python: consecutive_sell_range = (cs_min, cs_max); if not (cs_min <= consecutive_sell <= cs_max): return None
    if cfg.consecutive_sell_check_mode == CheckMode::Online {
        let consecutive_sell = recent_trades.iter().skip(1)
            .take_while(|rt| rt.trade_type != "buy" && rt.buy_amount.abs() >= cfg.consecutive_sell_threshold)
            .count() as i64;
        let (min_c, max_c) = cfg.consecutive_sell_range;
        if consecutive_sell < min_c || consecutive_sell > max_c {
            reject_reason = format!("连续卖单数量不在范围({}不在[{},{}])", consecutive_sell, min_c, max_c);
            return (false, reject_reason);
        }
    }
    
    // 条件16: 近N秒内交易单数量 (仅 Online 模式过滤)
    // Python: recent_trade_count = count trades in window; if not (rc_min <= count <= rc_max): return None
    if cfg.recent_trade_count_check_mode == CheckMode::Online {
        let current_time = *data.trade_miltime();
        let window_start = current_time.saturating_sub((cfg.recent_trade_count_window_seconds as u128) * 1000);
        let recent_count = recent_trades.iter()
            .filter(|rt| rt.swap_time >= window_start && rt.swap_time < current_time)
            .count();
        let (min_c, max_c) = cfg.recent_trade_count_range;
        if recent_count < min_c || recent_count > max_c {
            reject_reason = format!("近{}秒交易数量不在范围({}不在[{},{}])", 
                cfg.recent_trade_count_window_seconds, recent_count, min_c, max_c);
            return (false, reject_reason);
        }
    }
    
    // 条件17: 近N单平均交易间隔 (仅 Online 模式过滤)
    // Python: avg_interval = sum(intervals)/len(intervals); if not (ai_min <= avg <= ai_max): return None
    if cfg.avg_trade_interval_check_mode == CheckMode::Online {
        let current_time = *data.trade_miltime();
        let lookback = cfg.avg_trade_interval_lookback_count.min(recent_trades.len());
        if lookback >= 2 {
            let mut times: Vec<u128> = vec![current_time];
            times.extend(recent_trades.iter().take(lookback).map(|rt| rt.swap_time));
            
            let mut intervals: Vec<f64> = Vec::new();
            for i in 0..times.len() - 1 {
                intervals.push((times[i].saturating_sub(times[i + 1])) as f64);
            }
            
            if !intervals.is_empty() {
                let avg_interval = intervals.iter().sum::<f64>() / intervals.len() as f64;
                let (min_i, max_i) = cfg.avg_trade_interval_range;
                if avg_interval < min_i as f64 || avg_interval > max_i as f64 {
                    reject_reason = format!("平均交易间隔不在范围({:.0}ms不在[{},{}])", avg_interval, min_i, max_i);
                    return (false, reject_reason);
                }
            }
        }
    }
    
    // 条件18: 时间窗口内大额交易总和检查 (仅 Online 模式过滤)
    // Python: get_window_amount_sum - 在指定毫秒窗口内，过滤金额绝对值>=阈值的交易，计算金额总和
    if cfg.window_amount_sum_check_mode == CheckMode::Online {
        if let Some(ws) = features.window_amount_sum {
            let (min_s, max_s) = cfg.window_amount_sum_range;
            if ws < min_s || ws > max_s {
                reject_reason = format!("窗口内交易总和不在范围({:.2}不在[{:.2},{:.2}])", ws, min_s, max_s);
                return (false, reject_reason);
            }
        }
    }
    
    // 条件19: 时间窗口内大额交易买卖单数量检查 (仅 Online 模式过滤)
    // Python: get_window_buy_sell_count - 在指定毫秒窗口内，过滤金额绝对值>=阈值的交易，分别统计买卖单数量
    if cfg.window_buy_sell_count_check_mode == CheckMode::Online {
        if let Some(wbc) = features.window_buy_count {
            let (min_b, max_b) = cfg.window_buy_sell_count_buy_range;
            if wbc < min_b || wbc > max_b {
                reject_reason = format!("窗口内买单数量不在范围({}不在[{},{}])", wbc, min_b, max_b);
                return (false, reject_reason);
            }
        }
        if let Some(wsc) = features.window_sell_count {
            let (min_s, max_s) = cfg.window_buy_sell_count_sell_range;
            if wsc < min_s || wsc > max_s {
                reject_reason = format!("窗口内卖单数量不在范围({}不在[{},{}])", wsc, min_s, max_s);
                return (false, reject_reason);
            }
        }
    }
    
    // 所有 Online 模式条件都满足
    (true, String::new())
}

// =============================================================================
// 其他代码
// =============================================================================

pub struct QtfyNewAmmBuyStrategyDemo;

/// 买入特征快照结构体
#[derive(Debug, Clone, Default)]
pub struct BuyFeatures {
    // 基础信息
    pub mint: String,
    pub user: String,
    pub trade_type: String,
    
    // 时间特征
    pub time_from_creation_ms: u128,
    pub time_from_creation_min: f64,
    pub time_diff_from_last_trade_ms: f64,
    
    // 价格/市值特征
    pub current_price: f64,
    pub post_sol_amount: f32,
    pub sell_min_price: f64,
    pub sell_max_price: f64,
    
    // 交易特征
    pub trade_sol_amount: f32,
    pub trade_token_amount: f64,
    
    // 过滤交易统计
    pub filtered_trades_count: usize,
    pub filtered_trades_sum: f64,
    
    // 波动率特征
    pub price_volatility_cv: Option<f64>,
    pub time_volatility_cv: Option<f64>,
    pub amount_volatility_cv: Option<f64>,
    
    // 价格比率
    pub price_ratio: Option<f64>,
    
    // 交易计数
    pub buy_count: usize,
    pub sell_count: usize,
    pub consecutive_buy: usize,
    pub consecutive_sell: usize,
    
    // 大小单比例
    pub large_trade_ratio: Option<f64>,
    pub small_trade_ratio: Option<f64>,
    
    // 窗口特征 (条件18/19)
    pub window_amount_sum: Option<f64>,
    pub window_buy_count: Option<usize>,
    pub window_sell_count: Option<usize>,
    
    // 规则匹配
    pub matched_group: Option<usize>,
    pub matched_avg_profit: Option<f64>,
    pub buy_sol: f64,
}

impl BuyFeatures {
    pub fn to_log_string(&self) -> String {
        format!(
            "mint={} | user={} | type={} | time_create={:.2}min | time_diff={:.0}ms | price={:.10} | nowsol={:.2} | trade_sol={:.4} | filtered_cnt={} | filtered_sum={:.4} | price_cv={} | time_cv={} | amount_cv={} | price_ratio={} | buy_cnt={} | sell_cnt={} | consec_buy={} | consec_sell={} | large_ratio={} | small_ratio={} | win_amt_sum={} | win_buy={} | win_sell={} | matched_group={} | avg_profit={} | buy_sol={:.4}",
            self.mint,
            self.user,
            self.trade_type,
            self.time_from_creation_min,
            self.time_diff_from_last_trade_ms,
            self.current_price,
            self.post_sol_amount,
            self.trade_sol_amount,
            self.filtered_trades_count,
            self.filtered_trades_sum,
            self.format_opt(self.price_volatility_cv),
            self.format_opt(self.time_volatility_cv),
            self.format_opt(self.amount_volatility_cv),
            self.format_opt(self.price_ratio),
            self.buy_count,
            self.sell_count,
            self.consecutive_buy,
            self.consecutive_sell,
            self.format_opt(self.large_trade_ratio),
            self.format_opt(self.small_trade_ratio),
            self.format_opt(self.window_amount_sum),
            self.window_buy_count.map(|v| v.to_string()).unwrap_or("-".into()),
            self.window_sell_count.map(|v| v.to_string()).unwrap_or("-".into()),
            self.matched_group.map(|g| g.to_string()).unwrap_or("-".into()),
            self.format_opt(self.matched_avg_profit),
            self.buy_sol,
        )
    }
    
    fn format_opt(&self, val: Option<f64>) -> String {
        val.map(|v| format!("{:.4}", v)).unwrap_or("-".into())
    }
}

#[async_trait]
#[allow(unused_variables)]
impl PipelineHandler for QtfyNewAmmBuyStrategyDemo {
    async fn handle(&self, data: TradeContextNew) -> Option<TradeContextNew> {
        if let Some(mut watcher) = WATCH_CACHE.get_mut(data.trade_mint()) {
            let _beijing_time = chrono::DateTime::from_timestamp(*data.trade_time() as i64, 0)
                .map(|dt| dt.naive_utc())
                .and_then(|t| t.checked_add_signed(chrono::Duration::hours(8)))
                .map(|t| t.format("%Y-%m-%d %H:%M:%S").to_string())
                .unwrap_or_else(|| "Invalid timestamp".to_string());
            let mut can_buy = false;
            
            // 初始化特征
            let mut features = BuyFeatures {
                mint: data.trade_mint().to_string(),
                user: data.user().to_string(),
                trade_type: data.trade_type().to_string(),
                current_price: *data.price(),
                post_sol_amount: *data.post_sol_amount(),
                trade_sol_amount: *data.trade_sol_amount(),
                trade_token_amount: *data.trade_token_amount(),
                time_from_creation_ms: data.trade_miltime().saturating_sub(watcher.start_time),
                ..Default::default()
            };
            features.time_from_creation_min = features.time_from_creation_ms as f64 / 60000.0;
            
            if watcher.mint_status == MintStatus::Initial {
                if let Some(lianghua_watch) = xd_global_struct
                    .watching_bsc_mint_feed_info
                    .get(&data.trade_mint().to_string())
                {
                    // ...existing code...
                    let cfg = &*BUY_CONFIG;

                    let recent_trades: Vec<_> = lianghua_watch
                        .prepareTrade
                        .iter()
                        .take(200)
                        .collect();

                    
                    // 计算时间差特征
                    // Python: time_diff_from_last = tradetime - prev_tradetime
                    // recent_trades[1] 是最近一笔（当前交易的前一笔）
                    if let Some(rt0) = recent_trades.get(1) {
                        features.time_diff_from_last_trade_ms = data.trade_miltime().saturating_sub(rt0.swap_time) as f64;
                    }

                    // Helper: 计算变异系数 (coefficient of variation = std_dev / |mean|)
                    // 与 Python calculate_volatility 完全一致
                    let compute_cv = |vals: &[f64]| -> Option<f64> {
                        if vals.len() < 2 { return None; }
                        let mean = vals.iter().sum::<f64>() / vals.len() as f64;
                        if mean == 0.0 { return Some(0.0); }
                        let var = vals.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / vals.len() as f64;
                        Some(var.sqrt() / mean.abs())
                    };

                    // 计算波动率特征
                    // Python: get_recent_trades_volatility 过滤 abs(tradeamount) >= volatility_min_amount 的交易，
                    //         取前 volatility_lookback_count 笔有效交易（不含当前交易）
                    {
                        let vol_lookback = cfg.volatility_lookback_count;
                        let vol_min_amount = cfg.volatility_min_amount;
                        
                        let mut prices: Vec<f64> = Vec::new();
                        let mut time_intervals: Vec<f64> = Vec::new();
                        let mut amounts: Vec<f64> = Vec::new();
                        let mut prev_time: Option<f64> = None;
                        let mut valid_count = 0usize;
                        
                        // skip(1) 跳过 index 0（当前交易），与 Python 中从 i-1 开始遍历一致
                        for rt in recent_trades.iter().skip(1) {
                            if valid_count >= vol_lookback { break; }
                            let amount = rt.buy_amount.abs() as f64;
                            if amount < vol_min_amount as f64 { continue; }
                            valid_count += 1;
                            
                            // 价格波动率：使用价格字段
                            // Python: price = float(trade_data[i].get('price', 0))
                            // PrepareTradeMetrics 中用 post_sol_amount 作为价格代理
                            let price = rt.post_sol_amount as f64;
                            if price > 0.0 { prices.push(price); }
                            
                            // 时间波动率：计算相邻有效交易的时间间隔
                            let tradetime = rt.swap_time as f64;
                            if tradetime > 0.0 {
                                if let Some(pt) = prev_time {
                                    // 倒序遍历：prev_time 是较新交易的时间
                                    time_intervals.push(pt - tradetime);
                                }
                                prev_time = Some(tradetime);
                            }
                            
                            // 金额波动率
                            amounts.push(amount);
                        }
                        
                        features.price_volatility_cv = compute_cv(&prices);
                        features.time_volatility_cv = compute_cv(&time_intervals);
                        features.amount_volatility_cv = compute_cv(&amounts);
                    }

                    // 计算价格比率
                    // Python: get_price_ratio_to_min - 当前价格相对于近N单最低价的涨幅百分比
                    // price_ratio = (current_price / min_price - 1) * 100
                    {
                        let current_price = *data.price();
                        if current_price > 0.0 {
                            let pr_lookback = cfg.price_ratio_lookback_count;
                            let mut pr_prices: Vec<f64> = Vec::new();
                            for rt in recent_trades.iter().take(pr_lookback) {
                                // 使用 post_sol_amount 作为价格代理
                                let p = rt.post_sol_amount as f64;
                                if p > 0.0 { pr_prices.push(p); }
                            }
                            if !pr_prices.is_empty() {
                                let minp = pr_prices.iter().cloned().fold(f64::INFINITY, f64::min);
                                if minp > 0.0 {
                                    features.price_ratio = Some((*data.post_sol_amount() as f64 / minp - 1.0) * 100.0);
                                }
                            }
                        }
                    }

                    // 计算买卖计数
                    // Python: get_buy_sell_count 分别按各自的 lookback_count 计算（不含当前交易）
                    features.buy_count = recent_trades.iter().skip(1)
                        .take(cfg.buy_count_lookback_count)
                        .filter(|rt| rt.trade_type == "buy").count();
                    features.sell_count = recent_trades.iter().skip(1)
                        .take(cfg.sell_count_lookback_count)
                        .filter(|rt| rt.trade_type != "buy").count();
                    
                    // 计算连续大额买卖单
                    // Python: get_consecutive_buy_sell_count - 从当前位置向前，遇到不满足条件的就停止（不含当前交易）
                    features.consecutive_buy = recent_trades.iter().skip(1)
                        .take_while(|rt| rt.trade_type == "buy" && rt.buy_amount.abs() >= cfg.consecutive_buy_threshold)
                        .count();
                    features.consecutive_sell = recent_trades.iter().skip(1)
                        .take_while(|rt| rt.trade_type != "buy" && rt.buy_amount.abs() >= cfg.consecutive_sell_threshold)
                        .count();

                    // 计算大小单比例
                    // Python: get_large_small_trade_ratio - 使用 max(large_lookback, small_lookback) 的交易（不含当前交易）
                    {
                        let max_lookback = cfg.large_trade_ratio_lookback.max(cfg.small_trade_ratio_lookback).min(recent_trades.len().saturating_sub(1));
                        if max_lookback > 0 {
                            let large = recent_trades.iter().skip(1).take(max_lookback)
                                .filter(|rt| rt.buy_amount.abs() >= cfg.large_trade_threshold)
                                .count();
                            let small = recent_trades.iter().skip(1).take(max_lookback)
                                .filter(|rt| rt.buy_amount.abs() < cfg.small_trade_threshold)
                                .count();
                            features.large_trade_ratio = Some(large as f64 / max_lookback as f64);
                            features.small_trade_ratio = Some(small as f64 / max_lookback as f64);
                        }
                    }

                    // 计算过滤后的前N笔交易总和（不含当前交易）
                    // Python: get_filtered_trades_sum - 过滤 abs(amount) >= min_amount，取前 count 笔
                    //         直接累加原始 tradeamount（买入为正，卖出为负）
                    {
                        let mut c = 0usize;
                        let mut ssum = 0.0f64;
                        for rt in recent_trades.iter().skip(1) {
                            let amt = rt.buy_amount as f64;
                            if amt.abs() >= cfg.filtered_trades_min_amount as f64 {
                                // buy_amount 始终为正，需要根据 trade_type 确定符号
                                // Python: amount = float(trade_data[i].get('tradeamount', 0))
                                //         tradeamount 买入为正，卖出为负
                                if rt.trade_type == "buy" {
                                    ssum += amt.abs();
                                } else {
                                    ssum -= amt.abs();
                                }
                                c += 1;
                                if c >= cfg.filtered_trades_count {
                                    break;
                                }
                            }
                        }
                        features.filtered_trades_count = c;
                        features.filtered_trades_sum = ssum;
                    }

                    // 计算条件18: 时间窗口内大额交易总和
                    // Python: get_window_amount_sum
                    {
                        let current_time = *data.trade_miltime();
                        let window_start = current_time.saturating_sub(cfg.window_amount_sum_window_ms as u128);
                        let mut total_sum = 0.0f64;
                        let mut found_any = false;
                        for rt in recent_trades.iter() {
                            if rt.swap_time < window_start {
                                break;
                            }
                            let amt = rt.buy_amount.abs() as f64;
                            if amt >= cfg.window_amount_sum_min_amount as f64 {
                                if rt.trade_type == "buy" {
                                    total_sum += amt;
                                } else {
                                    total_sum -= amt;
                                }
                                found_any = true;
                            }
                        }
                        if found_any {
                            features.window_amount_sum = Some(total_sum);
                        }
                    }

                    // 计算条件19: 时间窗口内大额交易买卖单数量
                    // Python: get_window_buy_sell_count
                    {
                        let current_time = *data.trade_miltime();
                        let window_start = current_time.saturating_sub(cfg.window_buy_sell_count_window_ms as u128);
                        let mut win_buy = 0usize;
                        let mut win_sell = 0usize;
                        let mut found_any = false;
                        for rt in recent_trades.iter() {
                            if rt.swap_time < window_start {
                                break;
                            }
                            let amt = rt.buy_amount.abs() as f64;
                            if amt >= cfg.window_buy_sell_count_min_amount as f64 {
                                found_any = true;
                                if rt.trade_type == "buy" {
                                    win_buy += 1;
                                } else {
                                    win_sell += 1;
                                }
                            }
                        }
                        if found_any {
                            features.window_buy_count = Some(win_buy);
                            features.window_sell_count = Some(win_sell);
                        }
                    }

                    // 使用 check_buy_conditions 检查所有买入条件
                    let (conditions_ok, reject_reason) = check_buy_conditions(
                        &BUY_CONFIG,
                        &features,
                        &data,
                        &recent_trades,
                    );
                    // println!("条件检查结果: {}, reject_reason: {}", conditions_ok, reject_reason);

                    if conditions_ok {
                        // 设置默认买入金额
                        let buy_sol = 0.2f64;
                        features.buy_sol = buy_sol;

                        let mut trade_token_amount = (*data.trade_token_amount() as f64 * buy_sol * 1e-6)
                            / (*data.trade_sol_amount() as f64);
                        if trade_token_amount < 1000.0 {
                            trade_token_amount = trade_token_amount * 1e6;
                        }
                        can_buy = true;
                    } 

                    if can_buy {
                        let (sell_min_price, sell_max_price) = lianghua_watch
                            .price_history
                            .iter()
                            .skip(1)
                            .take(10)
                            .fold((f64::MAX, f64::MIN), |(min, max), info| {
                                (min.min(*info), max.max(*info))
                            });

                        features.sell_min_price = sell_min_price;
                        features.sell_max_price = sell_max_price;

                        watcher.timestamp = *data.trade_miltime();
                        watcher.mint_status = MintStatus::CanBuy;
                        watcher.hit_block_id = *data.block_time();
                        watcher.open_time = *data.trade_miltime();
                        watcher.start_price = *data.price();
                        watcher.start_post_sol = *data.post_sol_amount();
                        watcher.sell_min_price = sell_min_price as f64;

                        if watcher.is_test_trade {
                            let buy_snapshot = BuySnapshot {
                                post_sol: *data.post_sol_amount(),
                                open_time_stamp: *data.trade_miltime() - watcher.start_time,
                                buy_reason: "test_trade".into(),
                                trade_sol: *data.trade_sol_amount(),
                                buy_price: *data.price(),
                                last_trade_time: lianghua_watch.last_swap_time,
                                compute_unit_price: *data.compute_unit_price(),
                                swap_trade_buy_cnt: 0,
                                swap_trade_sell_cnt: 0,
                                total_swap_sol: 0.0,
                                cv: 0.0,
                            };
                            watcher.buy_snapshot = Some(buy_snapshot);
                        }

                        // 打印所有特征
                        tracing::warn!(
                            "[命中买入] {} | {} | sell_min={:.10} | sell_max={:.10} | https://gmgn.ai/sol/token/{}",
                            _beijing_time,
                            features.to_log_string(),
                            sell_min_price,
                            sell_max_price,
                            data.trade_mint(),
                        );

                        watcher.group_full_name = format!("{}-{}", data.trade_type(), data.trade_mint());
                        watcher.max_open_time = 2 * 60 * 1000;
                        watcher.start_sol = *data.trade_sol_amount();
                        watcher.is_fake_trade = false;

                        // ...existing code for GROUP_CACHE check...
                        let record = GROUP_CACHE.get(&watcher.group_full_name.clone());
                        if let Some(rd) = record {
                            let fail_cnt = rd.group_max_rate_record.iter().take(3).filter(|&&rate| rate < -20.0).count();
                            let succ_cnt = rd.group_max_rate_record.iter().take(7).filter(|&&rate| rate > 5.0).count();
                            let succ_cnt2 = rd.group_max_rate_record.iter().take(15).filter(|&&rate| rate > 5.0).count();
                            if fail_cnt >= 1 {
                                watcher.test_hit_zs_buy = true;
                                watcher.is_fake_trade = true;
                            }
                        }
                        if watcher.is_test_trade {
                            watcher.is_fake_trade = true;
                        } else {
                            watcher.sell_level = 1;
                        }
                    }
                }
            }
            // ...existing code for CanBuy status handling...
            let self_wallets = vec![
                "AJ8Gc1cYzDQmQVyWFnHyJAKV5QK5ysz5ML9NuK3xvJRt".to_string(),
            ];
            if watcher.mint_status == MintStatus::CanBuy {
                if watcher.is_fake_trade
                    && ((data.user().to_string()
                        == "omegoMAe1AMY5MFKQQr3JwXVy8F4eCvmBAfcpo8XAfq".to_string()
                        && false)
                        || self_wallets.contains(&data.user().to_string())
                        || *data.trade_miltime() >= watcher.timestamp + 100)
                {
                    let group_full_name = "xd_global_group".to_string();
                    let mut record = GROUP_CACHE
                        .entry(group_full_name.clone())
                        .or_insert_with(UnifyRecordContext::new);

                    if true {
                        record.group_buyed_mint.push_front(data.trade_mint().to_string());
                    }

                    watcher.mint_status = MintStatus::IsBuyed;
                    watcher.buy_sol_amount = *data.trade_sol_amount();
                    watcher.open_time = *data.trade_miltime();
                    watcher.final_hit_buy_user = *data.user();
                    watcher.final_hit_buy_time = data.trade_miltime().saturating_sub(watcher.timestamp);
                    watcher.final_hit_buy_price = *data.price();
                    watcher.max_open_time = 2 * 60 * 1000;
                } else if watcher.is_fake_trade
                    && (*data.trade_miltime() < watcher.timestamp + 120
                        || *data.trade_miltime() > watcher.timestamp + 1000)
                {
                    watcher.start_price = *data.price();
                    watcher.start_post_sol = *data.post_sol_amount();
                } else if !watcher.is_fake_trade && !watcher.is_test_trade {
                    let buyed_sol = 0.4;
                    let mut trade_token_amount = (*data.trade_token_amount() as f64 * buyed_sol * 1e-6) / (*data.trade_sol_amount() as f64);
                    if trade_token_amount < 1000.0 {
                        trade_token_amount = trade_token_amount * 1e6;
                    }

                    if MINT_CACHE2.entry_count() <= 20 {
                        UNIFY_BUY_CHANNEL
                            .sender
                            .send(TradeMessage::AmountMessage(data.clone(), trade_token_amount, watcher.timestamp, watcher.max_open_time))
                            .unwrap();
                        tracing::info!(
                            "[正式买入] 当前 {} 允许直接买入, 交易金额：{} https://gmgn.ai/sol/token/{}",
                            watcher.group_full_name, data.trade_sol_amount(), data.trade_mint()
                        );
                        watcher.mint_status = MintStatus::IsBuying;
                        watcher.start_price = *data.price();
                        watcher.start_post_sol = *data.post_sol_amount();
                        watcher.open_time = *data.trade_miltime();
                    } else {
                        watcher.mint_status = MintStatus::IsSelled;
                        tracing::warn!("当前 持仓 数量超过限制，无法买入! {}", data.trade_mint());
                    }
                }
            }
        }

        Some(data)
    }
}
