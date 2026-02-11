use crate::{
    context::{self, context::TradeContextNew, context_new::MintStatus, trader::TradeMessage},
    help::{
        global::{global_struct, UNIFY_SELL_CHANNEL, WATCH_CACHE}, global_xd::xd_global_struct, tool::get_current_milsec
    },
    processer::PipelineHandler,
};
use async_trait::async_trait;
use std::io::Write;
use serde::Deserialize;

// =============================================================================
// 卖出条件配置结构体 - 从 sell_rules.json 加载
// =============================================================================
#[derive(Debug, Deserialize, Clone)]
pub struct SellConditionsConfig {
    pub max_nowsol_sell: f32,           // 市值止盈阈值
    pub profit_rate_sell_enabled: bool, // 是否启用盈利率止盈
    pub profit_rate_sell_threshold: f64, // 盈利率止盈阈值 (0.9 = 90%)
    pub loss_percentage: f64,           // 亏损止损比例 (0.45 = 45%)
    pub lookback_trades_for_min_price: usize, // 买入前回看笔数取最低价
    pub retracement_low_profit: f64,    // 低利润回撤止损比例 (0.05 = 5%)
    pub retracement_high_profit: f64,   // 高利润回撤止损比例 (0.05 = 5%)
    pub high_profit_threshold: f64,     // 高低利润分界阈值 (0.4 = 40%)
    pub retracement_min_count: usize,   // 回撤区间内拐点次数阈值
    pub retracement_inflection_window: usize, // 拐点检测窗口大小
    pub retracement_min_hold_ms: u64,   // 回撤止损最小持有时间（毫秒）
    pub retracement_min_profit: f64,    // 回撤止损最小盈利阈值 (0.05 = 5%)
    pub sell_pressure_enabled: bool,    // 是否启用卖压检测
    pub sell_pressure_lookback: usize,  // 卖压检测近N单
    pub sell_pressure_sum_threshold: f32, // 近N单总和阈值
    pub sell_pressure_all_sell: bool,   // 近N单全是卖单时卖出
    pub max_hold_time_seconds: u64,     // 最大持仓秒数
    pub quiet_period_enabled: bool,     // 是否启用冷淡期卖出
    pub quiet_period_seconds: u64,      // 冷淡期检测窗口(秒)
    pub quiet_period_min_amount: f32,   // 冷淡期大单阈值(SOL)
    pub spike_sell_enabled: bool,       // 是否启用短期暴涨卖出
    pub spike_lookback_ms: u64,         // 短期暴涨回看时间窗口(毫秒)
    pub spike_threshold_pct: f64,       // 短期暴涨阈值百分比
    pub rebound_sell_enabled: bool,     // 是否启用反弹卖出
    pub rebound_min_loss_pct: f64,      // 反弹卖出最低亏损阈值百分比
    pub rebound_min_profit_pct: f64,    // 反弹卖出盈利阈值百分比
    pub rebound_min_buy_amount: f32,    // 反弹卖出触发的最小买单金额(SOL)
    // 活跃期高涨幅卖出
    pub active_spike_sell_enabled: bool,    // 是否启用
    pub active_spike_window_seconds: u64,   // 时间窗口（秒）
    pub active_spike_min_trade_count: usize,// 时间窗口内最少交易单数
    pub active_spike_lookback_count: usize, // 计算最低价的近N单
    pub active_spike_min_rise_pct: f64,     // 距最低价的最小涨幅百分比
    // 低活跃涨幅卖出
    pub inactive_spike_sell_enabled: bool,    // 是否启用
    pub inactive_spike_window_seconds: u64,   // 时间窗口（秒）
    pub inactive_spike_max_trade_count: usize,// 时间窗口内最多交易单数（低于此值视为低活跃）
    pub inactive_spike_lookback_count: usize, // 计算最低价的近N单
    pub inactive_spike_min_rise_pct: f64,     // 距最低价的最小涨幅百分比
}

#[derive(Debug, Deserialize)]
struct SellRulesFile {
    sell_conditions: SellConditionsConfig,
}

impl SellConditionsConfig {
    /// 从 sell_rules.json 加载配置，失败则使用默认值
    pub fn load_from_json(path: &str) -> Self {
        match std::fs::read_to_string(path) {
            Ok(content) => {
                match serde_json::from_str::<SellRulesFile>(&content) {
                    Ok(rules) => {
                        tracing::info!("卖出规则加载成功: {}", path);
                        rules.sell_conditions
                    }
                    Err(e) => {
                        tracing::error!("解析卖出规则JSON失败: {}, 使用默认值", e);
                        Self::default()
                    }
                }
            }
            Err(e) => {
                tracing::error!("读取卖出规则文件失败: {}, 使用默认值", e);
                Self::default()
            }
        }
    }

    fn default() -> Self {
        Self {
            max_nowsol_sell: 300.0,
            profit_rate_sell_enabled: true,
            profit_rate_sell_threshold: 0.9,    // 盈利率 >= 90% 时直接卖出
            loss_percentage: 0.45,              // 亏损达到 45% 时触发止损
            lookback_trades_for_min_price: 5,
            retracement_low_profit: 0.05,       // 最大盈利 < 40% 时，回撤 5% 卖出
            retracement_high_profit: 0.05,      // 最大盈利 >= 40% 时，回撤 5% 卖出
            high_profit_threshold: 0.40,        // 高盈利阈值 40%
            retracement_min_count: 0,           // 拐点次数阈值
            retracement_inflection_window: 5,   // 拐点检测窗口大小
            retracement_min_hold_ms: 60000,     // 回撤止损最小持有时间 60秒
            retracement_min_profit: 0.05,       // 回撤止损最小盈利阈值 5%
            sell_pressure_enabled: false,
            sell_pressure_lookback: 10,
            sell_pressure_sum_threshold: -20.0,
            sell_pressure_all_sell: false,
            max_hold_time_seconds: 3000,
            quiet_period_enabled: false,
            quiet_period_seconds: 20,
            quiet_period_min_amount: 0.8,
            spike_sell_enabled: true,
            spike_lookback_ms: 400,
            spike_threshold_pct: 8.0,
            rebound_sell_enabled: true,
            rebound_min_loss_pct: 7.0,
            rebound_min_profit_pct: 5.0,
            rebound_min_buy_amount: 3.5,
            // 活跃期高涨幅卖出
            active_spike_sell_enabled: true,
            active_spike_window_seconds: 2,
            active_spike_min_trade_count: 20,
            active_spike_lookback_count: 35,
            active_spike_min_rise_pct: 15.0,
            // 低活跃涨幅卖出
            inactive_spike_sell_enabled: true,
            inactive_spike_window_seconds: 3,
            inactive_spike_max_trade_count: 5,
            inactive_spike_lookback_count: 20,
            inactive_spike_min_rise_pct: 8.0,
        }
    }
}

// // 全局卖出配置 (延迟初始化)
// lazy_static::lazy_static! {
//     static ref SELL_CONFIG: SellConditionsConfig = SellConditionsConfig::load_from_json("sell_rules.json");
// }

/// 量化卖出策略 - 对应 Python variant_find_sell_signal 的6个卖出条件
pub struct PumpQtfySellProcesserDemo;

#[async_trait]
impl PipelineHandler for PumpQtfySellProcesserDemo {
    async fn handle(&self, data: TradeContextNew) -> Option<TradeContextNew> {
        let mut need_remove = false;
        let mut need_sell = false;
        if let Some(mut indicator) = WATCH_CACHE.get_mut(data.trade_mint()) {

            indicator.cur_sol_amount = data.post_sol_amount().clone();
            indicator.last_swap_type = data.trade_type().to_string().clone();

            if (indicator.mint_status != MintStatus::IsBuyed && indicator.mint_status != MintStatus::IsSelling) || *data.trade_sol_amount() < 0.01 || *data.trade_token_amount() < 100.0  {
                return Some(data);
            }

            let mut sell_reason = String::new();
            let beijing_time =
                        chrono::NaiveDateTime::from_timestamp_opt(*data.trade_time() as i64, 0)
                            .map(|t| {
                                (t + chrono::Duration::hours(8))
                                    .format("%Y-%m-%d %H:%M:%S")
                                    .to_string()
                            })
                            .unwrap_or_else(|| "Invalid timestamp".to_string());

                // 重写触发价格和时间 (首笔交易初始化)
                if indicator.swap_cnt < 1 {
                    indicator.start_price = data.price().clone();
                    indicator.open_time = data.trade_miltime().clone();
                    indicator.rate = 0.0;
                    indicator.max_rate = 0.0;
                    indicator.min_rate = 0.0;
                    indicator.max_price = *data.price();
                    indicator.min_price = *data.price();
                }

                let key = data.trade_mint().to_string();
            if let Some(mut watching_feed) = xd_global_struct
                .watching_bsc_mint_feed_info
                .get_mut(key.as_str())
            {
                let feed = watching_feed.value_mut();
                if feed.is_black_source > 0 {
                    need_sell = true;
                    sell_reason += &format!("命中拉黑卖出,拉黑类型{}|", feed.is_black_source);
                }

                let cfg = SellConditionsConfig::default(); //&*SELL_CONFIG;
                let current_miltime = *data.trade_miltime();
                let current_price = *data.price();
                let current_nowsol = *data.post_sol_amount();
                let current_trade_amount = *data.trade_sol_amount(); // 始终为正
                let is_sell_trade = data.trade_type() == "sell";
                let buy_price = indicator.start_price; // 买入时的价格
                let buy_time = indicator.open_time;    // 买入时的时间(毫秒)

                // 更新价格极值
                let rate;
                if current_price != 0.0 {
                    rate = 100.0 * (current_price / buy_price - 1.0);
                    if rate < -60.0 {
                        indicator.rate = 0.0;
                        indicator.swap_cnt += 1;
                        return Some(data);
                    }
                    indicator.rate = rate;
                } else {
                    rate = indicator.rate;
                }

                if current_price > indicator.max_price {
                    indicator.max_price = current_price;
                }
                if current_price < indicator.min_price || indicator.min_price == 0.0 {
                    indicator.min_price = current_price;
                }
                indicator.max_rate = indicator.max_rate.max(rate);

                // 统计买卖单
                if data.trade_type() == "buy" {
                    if current_trade_amount > 0.4 {
                        indicator.big_buy_cnt += 1;
                    } else {
                        indicator.small_buy_cnt += 1;
                    }
                }
                if data.trade_type() == "sell" {
                    if current_trade_amount > 1.0 {
                        indicator.big_sell_cnt += 1;
                    } else {
                        indicator.small_sell_cnt += 1;
                    }
                }

                indicator.swap_cnt += 1;

                // 计算当前盈亏比例 (与Python一致: (current_price - buy_price) / buy_price)
                let current_profit_rate = if buy_price > 0.0 {
                    (current_price as f64 - buy_price as f64) / buy_price as f64
                } else {
                    0.0
                };

                // 最大盈利率 (比例，非百分比)
                let max_profit_rate = if buy_price > 0.0 {
                    (indicator.max_price as f64 - buy_price as f64) / buy_price as f64
                } else {
                    0.0
                };

                // 更新最低盈利率（用于反弹卖出检测）
                if indicator.min_profit_rate > current_profit_rate {
                    indicator.min_profit_rate = current_profit_rate;
                }
                // 检查是否曾经亏损超过阈值
                let rebound_min_loss = cfg.rebound_min_loss_pct / 100.0;
                let has_experienced_loss = indicator.min_profit_rate <= -rebound_min_loss;

                // =============================================================
                // 条件1: 市值止盈
                // Python: if current_nowsol >= max_nowsol_sell: return "市值止盈"
                // =============================================================
                if current_nowsol >= cfg.max_nowsol_sell {
                    sell_reason += &format!("市值止盈(nowsol={:.2}>={})|", current_nowsol, cfg.max_nowsol_sell);
                    need_sell = true;
                }

                // =============================================================
                // 条件1.5: 盈利率止盈
                // Python: if profit_rate_sell_enabled and current_profit_rate >= profit_rate_sell_threshold:
                //             return "盈利率止盈"
                // =============================================================
                if !need_sell && cfg.profit_rate_sell_enabled && current_profit_rate >= cfg.profit_rate_sell_threshold {
                    sell_reason += &format!(
                        "盈利率止盈(盈利{:.2}%>={:.0}%)|",
                        current_profit_rate * 100.0,
                        cfg.profit_rate_sell_threshold * 100.0
                    );
                    need_sell = true;
                }

                // =============================================================
                // 条件1.6: 卖压止损
                // Python: if sell_pressure_enabled:
                //           检查近N单是否全是卖单，或总和 < 阈值
                // =============================================================
                if !need_sell && cfg.sell_pressure_enabled {
                    let prepare_trades = &feed.prepareTrade;
                    let lookback = cfg.sell_pressure_lookback.min(prepare_trades.len());
                    
                    if lookback >= cfg.sell_pressure_lookback {
                        let mut all_sell = true;
                        let mut total_sum: f32 = 0.0;
                        
                        for pt in prepare_trades.iter().take(lookback) {
                            // is_buy 为 false 表示卖单
                            if pt.trade_type== "buy" {
                                all_sell = false;
                            }
                            // 卖单为负，买单为正
                            let amt = if pt.trade_type== "buy" { pt.buy_amount } else { -pt.buy_amount };
                            total_sum += amt;
                        }
                        
                        if cfg.sell_pressure_all_sell && all_sell {
                            sell_reason += &format!(
                                "卖压止损(近{}单全是卖单)|",
                                cfg.sell_pressure_lookback
                            );
                            need_sell = true;
                        } else if total_sum < cfg.sell_pressure_sum_threshold {
                            sell_reason += &format!(
                                "卖压止损(近{}单总和{:.2}SOL<{:.1}SOL)|",
                                cfg.sell_pressure_lookback, total_sum, cfg.sell_pressure_sum_threshold
                            );
                            need_sell = true;
                        }
                    }
                }

                // =============================================================
                // 条件2: 亏损止损
                // Python: if current_profit_rate <= -loss_percentage:
                //             if current_price < min_price_before_buy: return "亏损止损"
                // min_price_before_buy = 买入前 lookback_trades_for_min_price 笔交易的最低价
                // prepareTrade 以 push_front 方式存储，index 0 = 最新
                // 买入时的历史交易在 prepareTrade 中较靠后的位置
                // =============================================================
                if !need_sell && current_profit_rate <= -(cfg.loss_percentage) {
                    // 从 prepareTrade 中获取买入前的最低价
                    // prepareTrade[0] 是最新交易，越往后越早
                    // 我们需要找到买入时间之前的交易，取最近 lookback 笔的最低价
                    let mut min_price_before_buy: Option<f64> = None;
                    // if let Some(lianghua_watch) = WATCH_CACHE.get(data.trade_mint()) {
                        let prepare_trades = &feed.prepareTrade;
                        let mut count = 0usize;
                        for pt in prepare_trades.iter() {
                            // 只看买入时间之前的交易
                            if pt.swap_time >= buy_time {
                                continue;
                            }
                            // 通过 post_sol_amount 估算价格（因为 PrepareTradeMetrics 没有 price 字段）
                            // 使用 post_sol_amount 作为价格代理，或者如果有其他字段
                            // 注意: PrepareTradeMetrics 没有 price 字段，这里使用 indicator 记录的 sell_min_price
                            // 作为替代方案，我们记录买入前的最低价到 indicator 中
                            count += 1;
                            if count >= cfg.lookback_trades_for_min_price {
                                break;
                            }
                        }
                    // }
                    // 使用 indicator.sell_min_price 作为买入前最低价的代理
                    // (在买入时应该已经计算并存储了)
                    if indicator.sell_min_price > 0.0 && current_price < indicator.sell_min_price {
                        sell_reason += &format!(
                            "亏损止损(rate={:.2}%,price={:.6}<min={:.6})|",
                            current_profit_rate * 100.0, current_price, indicator.sell_min_price
                        );
                        need_sell = true;
                    }
                }

                // =============================================================
                // 条件3+4: 回撤止损 (低利润/高利润) - 带拐点检测
                // Python:
                //   需要满足：最小持有时间 且 当前盈利 >= 最小盈利阈值
                //   if max_price > buy_price and hold_time_ms >= retracement_min_hold_ms 
                //      and current_profit_rate >= retracement_min_profit:
                //     retracement = (max_price - current_price) / max_price
                //     使用窗口判断拐点：如果窗口中间位置是最大值，则为拐点
                //     拐点次数 >= retracement_min_count 时触发卖出
                // =============================================================
                let hold_time_ms_for_retracement = current_miltime.saturating_sub(buy_time);
                if !need_sell && indicator.max_price as f64 > buy_price as f64 
                    && hold_time_ms_for_retracement >= cfg.retracement_min_hold_ms as u128
                    && current_profit_rate >= cfg.retracement_min_profit {
                    let retracement = (indicator.max_price as f64 - current_price as f64)
                        / indicator.max_price as f64;

                    // 判断当前回撤阈值
                    let retracement_threshold = if max_profit_rate < cfg.high_profit_threshold {
                        cfg.retracement_low_profit
                    } else {
                        cfg.retracement_high_profit
                    };

                    if retracement >= retracement_threshold {
                        // 从 price_history 历史数据计算拐点次数
                        let window_size = cfg.retracement_inflection_window;
                        let mut inflection_count = 0usize;
                        
                        // 获取最近的价格历史
                        let price_history: Vec<f64> = feed.price_history
                            .iter()
                            .take(80) // 最多取最近80笔交易的价格历史
                            .cloned()
                            .collect();
                        
                        // 检测拐点：滑动窗口检测局部最大值
                        if price_history.len() >= window_size {
                            for i in 0..=(price_history.len() - window_size) {
                                let window: Vec<f64> = price_history[i..i+window_size].to_vec();
                                let mid_index = window_size / 2;
                                if let Some(&mid_price) = window.get(mid_index) {
                                    let max_in_window = window.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
                                    let first_price = window.first().copied().unwrap_or(0.0);
                                    let last_price = window.last().copied().unwrap_or(0.0);
                                    
                                    // 如果中间位置是窗口内最大值，则认为是拐点
                                    if (mid_price - max_in_window).abs() < 1e-10
                                        && mid_price > first_price 
                                        && mid_price > last_price 
                                    {
                                        inflection_count += 1;
                                    }
                                }
                            }
                        }

                        // 拐点计数达到阈值则卖出
                        if inflection_count >= cfg.retracement_min_count {
                            if max_profit_rate < cfg.high_profit_threshold {
                                sell_reason += &format!(
                                    "回撤止损(低)(retracement={:.2}%>={:.2}%,max_profit={:.2}%,拐点{}次)|",
                                    retracement * 100.0,
                                    cfg.retracement_low_profit * 100.0,
                                    max_profit_rate * 100.0,
                                    inflection_count
                                );
                            } else {
                                sell_reason += &format!(
                                    "回撤止损(高)(retracement={:.2}%>={:.2}%,max_profit={:.2}%,拐点{}次)|",
                                    retracement * 100.0,
                                    cfg.retracement_high_profit * 100.0,
                                    max_profit_rate * 100.0,
                                    inflection_count
                                );
                            }
                            need_sell = true;
                        }
                    }
                }

                // =============================================================
                // 条件5: 时间止损
                // Python: hold_time_seconds = (current_time - buy_time) / 1000
                //         if hold_time_seconds > max_hold_seconds: return "时间止损"
                // =============================================================
                if !need_sell {
                    let hold_time_ms = current_miltime.saturating_sub(buy_time);
                    let hold_time_seconds = hold_time_ms / 1000;
                    if hold_time_seconds > cfg.max_hold_time_seconds as u128 {
                        sell_reason += &format!(
                            "时间止损(hold={}s>{}s)|",
                            hold_time_seconds, cfg.max_hold_time_seconds
                        );
                        need_sell = true;
                    }
                }

                // =============================================================
                // 条件6: 冷淡期卖出
                // Python:
                //   if quiet_period_enabled and current_tradeamount < 0:
                //     只有在持有时间 >= quiet_period_seconds 后才检查
                //     在过去 quiet_period_seconds 秒内，如果没有金额 >= quiet_period_min_amount 的交易
                //     则卖出
                // =============================================================
                if !need_sell && cfg.quiet_period_enabled && is_sell_trade {
                    let hold_time_ms = current_miltime.saturating_sub(buy_time);
                    let hold_time_seconds = hold_time_ms / 1000;
                    
                    // 只有持有时间超过冷淡期时间窗口后才检查
                    if hold_time_seconds >= cfg.quiet_period_seconds as u128 {
                        let quiet_window_ms = (cfg.quiet_period_seconds as u128) * 1000;
                        let quiet_start_time = current_miltime.saturating_sub(quiet_window_ms);

                        let mut has_large_trade = false;

                        // prepareTrade 以 push_front 存储: index 0 = 最新交易
                        // 遍历历史交易，查找窗口内是否有大单
                        let prepare_trades = &feed.prepareTrade;
                        for pt in prepare_trades.iter() {
                            // 跳过当前交易本身 (swap_time == current_miltime 的)
                            if pt.swap_time >= current_miltime {
                                continue;
                            }
                            // 超出时间窗口则停止
                            if pt.swap_time < quiet_start_time {
                                break;
                            }
                            // 只看买入之后的交易
                            if pt.swap_time <= buy_time {
                                break;
                            }
                            // 检查金额是否 >= 阈值 (buy_amount 始终为正)
                            if pt.buy_amount >= cfg.quiet_period_min_amount {
                                has_large_trade = true;
                                break;
                            }
                        }

                        if !has_large_trade {
                            sell_reason += &format!(
                                "冷淡期卖出(持有{}s,{}s内无>={:.2}SOL交易)|",
                                hold_time_seconds, cfg.quiet_period_seconds, cfg.quiet_period_min_amount
                            );
                            need_sell = true;
                        }
                    }
                }

                // =============================================================
                // 条件7: 短期暴涨卖出
                // Python: if spike_sell_enabled and current_profit_rate > 0:
                //     从当前交易向前找到 spike_lookback_ms 之前的那笔交易价格
                //     spike_pct = (current_price - ref_price) / ref_price * 100
                //     如果 spike_pct >= spike_threshold_pct: 卖出
                // =============================================================
                if !need_sell && cfg.spike_sell_enabled && current_profit_rate > 0.0 {
                    let spike_start_time = current_miltime.saturating_sub(cfg.spike_lookback_ms as u128);
                    let mut ref_price: Option<f64> = None;

                    // 从最近的交易向前遍历，找到第一个时间 <= spike_start_time 的交易
                    // Python: for j in range(i - 1, buy_index - 1, -1):
                    //             if prev_time <= spike_start_time: ref_price = price; break
                    let prepare_trades = &feed.prepareTrade;
                    for pt in prepare_trades.iter() {
                        // 跳过当前交易之后的数据
                        if pt.swap_time >= current_miltime {
                            continue;
                        }
                        // 只看买入之后的交易
                        if pt.swap_time < buy_time {
                            break;
                        }
                        // 找到第一笔时间 <= spike_start_time 的交易
                        if pt.swap_time <= spike_start_time {
                            ref_price = Some(pt.price as f64);
                            break;
                        }
                    }

                    if let Some(rp) = ref_price {
                        if rp > 0.0 {
                            // Python: spike_pct = (current_price - ref_price) / ref_price * 100
                            let spike_pct = (current_price as f64 - rp) / rp * 100.0;
                            if spike_pct >= cfg.spike_threshold_pct {
                                sell_reason += &format!(
                                    "短期暴涨卖出(近{}ms涨幅{:.2}%>={:.1}%)|",
                                    cfg.spike_lookback_ms, spike_pct, cfg.spike_threshold_pct
                                );
                                need_sell = true;
                            }
                        }
                    }
                }

                // =============================================================
                // 条件8: 反弹卖出
                // Python: if rebound_sell_enabled and has_experienced_loss:
                //     if current_profit_rate >= rebound_min_profit_pct / 100:
                //         if current_tradeamount >= rebound_min_buy_amount: 卖出
                // has_experienced_loss = 曾经亏损超过 rebound_min_loss_pct
                // =============================================================
                if !need_sell && cfg.rebound_sell_enabled && has_experienced_loss {
                    let rebound_min_profit = cfg.rebound_min_profit_pct / 100.0;
                    if current_profit_rate >= rebound_min_profit {
                        // Python: current_tradeamount >= rebound_min_buy_amount
                        // 在Python中 tradeamount 买入为正，这里只检查买单
                        if !is_sell_trade && current_trade_amount >= cfg.rebound_min_buy_amount {
                            sell_reason += &format!(
                                "反弹卖出(最低亏损{:.2}%>={:.0}%,反弹至盈利{:.2}%>={:.0}%,买单{:.2}>={:.1}SOL)|",
                                indicator.min_profit_rate.abs() * 100.0,
                                cfg.rebound_min_loss_pct,
                                current_profit_rate * 100.0,
                                cfg.rebound_min_profit_pct,
                                current_trade_amount,
                                cfg.rebound_min_buy_amount
                            );
                            need_sell = true;
                        }
                    }
                }

                // =============================================================
                // 条件9: 活跃期高涨幅卖出
                // Python: if active_spike_sell_enabled and current_profit_rate > 0:
                //     统计近 active_spike_window_seconds 秒内交易笔数
                //     如果 >= active_spike_min_trade_count:
                //         取近 active_spike_lookback_count 单(买入后)的最低价
                //         rise_pct = (current_price - min_price) / min_price * 100
                //         如果 rise_pct >= active_spike_min_rise_pct: 卖出
                // =============================================================
                if !need_sell && cfg.active_spike_sell_enabled && current_profit_rate > 0.0 {
                    let window_start = current_miltime.saturating_sub((cfg.active_spike_window_seconds as u128) * 1000);
                    let mut recent_count: usize = 0;

                    let prepare_trades = &feed.prepareTrade;
                    // 统计时间窗口内交易笔数
                    for pt in prepare_trades.iter() {
                        if pt.swap_time >= current_miltime { continue; }
                        if pt.swap_time < buy_time { break; }
                        if pt.swap_time < window_start { break; }
                        recent_count += 1;
                    }

                    if recent_count >= cfg.active_spike_min_trade_count {
                        // 取近 lookback_count 单(买入后的)最低价
                        // Python: 使用 trade_data[j]['price']，Rust 使用 pt.price
                        let mut low_prices: Vec<f64> = Vec::new();
                        let mut cnt = 0usize;
                        for pt in prepare_trades.iter() {
                            if pt.swap_time >= current_miltime { continue; }
                            if pt.swap_time < buy_time { break; }
                            let p = pt.price as f64;
                            if p > 0.0 {
                                low_prices.push(p);
                            }
                            cnt += 1;
                            if cnt >= cfg.active_spike_lookback_count { break; }
                        }

                        if !low_prices.is_empty() {
                            let min_recent_price = low_prices.iter().cloned().fold(f64::INFINITY, f64::min);
                            if min_recent_price > 0.0 {
                                // Python: (current_price - min_recent_price) / min_recent_price * 100
                                let rise_pct = (current_price as f64 - min_recent_price) / min_recent_price * 100.0;
                                if rise_pct >= cfg.active_spike_min_rise_pct {
                                    sell_reason += &format!(
                                        "活跃期高涨幅卖出(近{}秒{}笔>={},距近{}单最低涨{:.2}%>={:.0}%)|",
                                        cfg.active_spike_window_seconds,
                                        recent_count,
                                        cfg.active_spike_min_trade_count,
                                        cfg.active_spike_lookback_count,
                                        rise_pct,
                                        cfg.active_spike_min_rise_pct
                                    );
                                    need_sell = true;
                                }
                            }
                        }
                    }
                }

                // =============================================================
                // 条件10: 低活跃涨幅卖出
                // Python: if inactive_spike_sell_enabled and current_profit_rate > 0:
                //     统计近 inactive_spike_window_seconds 秒内交易笔数
                //     如果 < inactive_spike_max_trade_count (低活跃):
                //         取近 inactive_spike_lookback_count 单(买入后)的最低价
                //         rise_pct = (current_price - min_price) / min_price * 100
                //         如果 rise_pct >= inactive_spike_min_rise_pct: 卖出
                // =============================================================
                if !need_sell && cfg.inactive_spike_sell_enabled && current_profit_rate > 0.0 {
                    let inactive_window_start = current_miltime.saturating_sub((cfg.inactive_spike_window_seconds as u128) * 1000);
                    let mut inactive_count: usize = 0;

                    let prepare_trades = &feed.prepareTrade;
                    // 统计时间窗口内交易笔数
                    for pt in prepare_trades.iter() {
                        if pt.swap_time >= current_miltime { continue; }
                        if pt.swap_time < buy_time { break; }
                        if pt.swap_time < inactive_window_start { break; }
                        inactive_count += 1;
                    }

                    // 低活跃：交易笔数 < 阈值
                    if inactive_count < cfg.inactive_spike_max_trade_count {
                        // 取近 lookback_count 单最低价
                        // Python: 使用 trade_data[j]['price']，Rust 使用 pt.price
                        let mut inactive_low_prices: Vec<f64> = Vec::new();
                        let mut cnt = 0usize;
                        for pt in prepare_trades.iter() {
                            if pt.swap_time >= current_miltime { continue; }
                            if pt.swap_time < buy_time { break; }
                            let p = pt.price as f64;
                            if p > 0.0 {
                                inactive_low_prices.push(p);
                            }
                            cnt += 1;
                            if cnt >= cfg.inactive_spike_lookback_count { break; }
                        }

                        if !inactive_low_prices.is_empty() {
                            let min_inactive_price = inactive_low_prices.iter().cloned().fold(f64::INFINITY, f64::min);
                            if min_inactive_price > 0.0 {
                                // Python: (current_price - min_price) / min_price * 100
                                let inactive_rise_pct = (current_price as f64 - min_inactive_price) / min_inactive_price * 100.0;
                                if inactive_rise_pct >= cfg.inactive_spike_min_rise_pct {
                                    sell_reason += &format!(
                                        "低活跃涨幅卖出(近{}秒仅{}笔<{},距近{}单最低涨{:.2}%>={:.0}%)|",
                                        cfg.inactive_spike_window_seconds,
                                        inactive_count,
                                        cfg.inactive_spike_max_trade_count,
                                        cfg.inactive_spike_lookback_count,
                                        inactive_rise_pct,
                                        cfg.inactive_spike_min_rise_pct
                                    );
                                    need_sell = true;
                                }
                            }
                        }
                    }
                }

                // =============================================================
                // 执行卖出
                // =============================================================
                let open_last_time = current_miltime.saturating_sub(indicator.open_time);

                if need_sell && indicator.mint_status == MintStatus::IsBuyed {
                    let delta_max = indicator.max_rate - indicator.rate;
                    let sell_reason_details = format!(
                        "reason_tags={} | rate={:.2}% | max_rate={:.2}% | delta={:.2}% | open_last_time={}ms | swap_cnt={} | big_buy_cnt={} | small_buy_cnt={} | big_sell_cnt={} | small_sell_cnt={} | continous_sell_cnt={} | continous_buy_cnt={} | sell_max_price={:.6} | sell_min_price={:.6} | last_big_buy_time={} | profit_rate={:.4}% | max_profit_rate={:.4}%",
                        sell_reason,
                        indicator.rate,
                        indicator.max_rate,
                        delta_max,
                        open_last_time,
                        indicator.swap_cnt,
                        indicator.big_buy_cnt,
                        indicator.small_buy_cnt,
                        indicator.big_sell_cnt,
                        indicator.small_sell_cnt,
                        indicator.continous_sell_cnt,
                        indicator.continous_buy_cnt,
                        indicator.sell_max_price,
                        indicator.sell_min_price,
                        indicator.last_big_buy_time,
                        current_profit_rate * 100.0,
                        max_profit_rate * 100.0
                    );

                    tracing::warn!(
                                "[{}]{} {},命中卖出策略 {}，当前涨幅:{}，最大涨幅{},用户{},购买金额{},大单数量{},小单数量{},卖单数量{},小卖单数量{} ",
                                data.trade_mint().to_string(),
                                beijing_time,
                                open_last_time,
                                sell_reason,
                                indicator.rate,
                                indicator.max_rate,
                                data.user().to_string(),
                                *data.trade_sol_amount(),
                                indicator.big_buy_cnt,
                                indicator.small_buy_cnt,
                                indicator.big_sell_cnt,
                                indicator.small_sell_cnt
                            );

                    if !indicator.is_fake_trade {
                        indicator.my_sell_time = *data.trade_miltime();
                        UNIFY_SELL_CHANNEL
                            .sender
                            .send(TradeMessage::AmountMessage(data.clone(), 0.2, 0, 0))
                            .unwrap();
                        indicator.mint_status = MintStatus::IsSelling;
                    } else {
                            if indicator.my_sell_time == 0 {
                                indicator.my_sell_time = *data.trade_miltime();
                            }

                            indicator.mint_status = MintStatus::IsSelling;

                            if let Some(buy_snapshot) = &indicator.buy_snapshot {
                                let log_msg = format!(
                                    "买入快照信息,交易币种:{} 开仓时间戳:{}，买入价格:{}，买入金额:{}，买入理由:{}，买入后市值:{}，买入时计算单价:{}，买入时买单次数:{}，买入时卖单次数:{}，买入时总交易量:{}，买入时交易量波动率:{};卖出时信息： 当前价格:{}，当前涨幅:{}，最大涨幅:{}，大单数量:{}，小单数量:{}，卖单数量:{}，小卖单数量:{},卖出理由:{} ",
                                    data.trade_mint().to_string(),
                                    buy_snapshot.open_time_stamp,
                                    buy_snapshot.buy_price,
                                    buy_snapshot.trade_sol,
                                    buy_snapshot.buy_reason,
                                    buy_snapshot.post_sol,
                                    buy_snapshot.compute_unit_price,
                                    buy_snapshot.swap_trade_buy_cnt,
                                    buy_snapshot.swap_trade_sell_cnt,
                                    buy_snapshot.total_swap_sol,
                                    buy_snapshot.cv,
                                    data.price(),
                                    indicator.rate,
                                    indicator.max_rate,
                                    indicator.big_buy_cnt,
                                    indicator.small_buy_cnt,
                                    indicator.big_sell_cnt,
                                    indicator.small_sell_cnt,
                                    sell_reason
                                );

                                if let Ok(mut file) = std::fs::OpenOptions::new()
                                    .create(true)
                                    .write(true)
                                    .append(true)
                                    .open("日志文件0113.log")
                                {
                                    if let Err(e) = writeln!(file, "{}", log_msg) {
                                        tracing::error!("写入日志文件失败: {}", e);
                                    }
                                } else {
                                    tracing::error!("无法打开或创建日志文件: 日志文件0113.log");
                                }
                            }
                    }

                    if rate > 0.0 {
                        indicator.win_last_time = open_last_time;
                    } else {
                        indicator.loss_last_time = open_last_time;
                    }
                    indicator.open_last_time = open_last_time;
                    indicator.end_post_sol = *data.post_sol_amount();
                    indicator.close_time = current_miltime;
                    indicator.is_selling = true;
                    if indicator.is_fake_trade {
                        indicator.is_selled = true;
                    }
                    indicator.last_swap_time = data.trade_miltime().clone();
                }
            }

            // 处理正在卖出状态的确认
            if indicator.is_fake_trade && indicator.mint_status == MintStatus::IsSelling {
                let self_wallets = vec![
                    "4WEbzvm5RzSnBB5jWbXoTyRg4RFkkX5XmEf2UxR4LcDR".to_string(),
                ];

                let open_last_time = data.trade_miltime().saturating_sub(indicator.open_time);

                if self_wallets.contains(&data.user().to_string())
                    || data.user().to_string() == "4VRpAHcpW6CrpLdxrBYkH6w959Zntnzyt4vfaFr56RKK"
                    || *data.post_sol_amount() < 1.5
                    || (indicator.my_sell_time > 0 && *data.trade_miltime() > indicator.my_sell_time + 100)
                {
                    indicator.mint_status = MintStatus::IsSelled;
                    indicator.real_sell_price = *data.price();
                    indicator.real_sell_time = *data.trade_miltime();
                    tracing::warn!(
                        "[{}] {} {} 卖出滑点300毫秒结束，当前最终涨幅:{}，最大涨幅{},用户{},购买金额{}-{} 当前价格 {} ,买入价格 {} ",
                        data.trade_mint().to_string(),
                        beijing_time,
                        open_last_time,
                        indicator.rate,
                        indicator.max_rate,
                        data.user().to_string(),
                        *data.trade_sol_amount(),
                        indicator.buy_sol_amount,
                        *data.price(),
                        indicator.start_price
                    );
                } else {
                    let rate1 = 100.0 * (*data.price() / indicator.start_price - 1.0);
                    indicator.rate = rate1;
                    indicator.hit_price = *data.price();
                }
            }
        }

        return Some(data);
    }
}