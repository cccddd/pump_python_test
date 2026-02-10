use std::fs;
use std::path::Path;

use crate::{
    context::{
        context::{BuySnapshot, GroupIndicator, TradeContextNew, UnifyRecordContext},
        context_new::MintStatus,
        trader::TradeMessage,
    },
    help::{
        global::{GROUP_CACHE, MINT_CACHE2, UNIFY_BUY_CHANNEL, WATCH_CACHE},
        global_xd::xd_global_struct,
    },
    processer::{
        pump_quantify_processer::qtfy_data_prepare_metrics_lianghua::StrictWPatternDetector,
        PipelineHandler,
    },
};
use async_trait::async_trait;
use chrono::Timelike;
use serde_json::Value;

pub struct QtfyNewStrategyDemo;

#[async_trait]
#[allow(unused_variables)]
impl PipelineHandler for QtfyNewStrategyDemo {
    async fn handle(&self, data: TradeContextNew) -> Option<TradeContextNew> {
        if let Some(mut watcher) = WATCH_CACHE.get_mut(data.trade_mint()) {
            let _beijing_time = chrono::NaiveDateTime::from_timestamp(*data.trade_time() as i64, 0)
                .checked_add_signed(chrono::Duration::hours(8))
                .map(|t| t.format("%Y-%m-%d %H:%M:%S").to_string())
                .unwrap_or_else(|| "Invalid timestamp".to_string());

            if watcher.mint_status == MintStatus::Initial {
                if let Some(lianghua_watch) = xd_global_struct
                    .watching_bsc_mint_feed_info
                    .get(&data.trade_mint().to_string())
                {
                    let post_sol_amount_ok =
                        *data.post_sol_amount() >= 100.0 && *data.post_sol_amount() <= 300.0;

                    let time_is_ok = *data.trade_miltime() > watcher.start_time + 3 * 60 * 1000;

                    let cue_trade_is_ok = *data.trade_sol_amount() > 4.5
                        && *data.trade_sol_amount() < 10.0
                        && data.trade_type() == "sell";

                    let recent_trades: Vec<_> = lianghua_watch
                        .prepareTrade
                        .iter()
                        .take(200)
                        .collect();

                    // --- load merged rules from rule.json (expect grouped format with "params" and "conditions")
                    let mut matched_group: Option<&Value> = None;
                    let mut matched_bucket_avg_profit: Option<f64> = None;
                    let rule_path = Path::new("/Users/xcold/Desktop/pump_python_test/rule.json");
                    if rule_path.exists() {
                        if let Ok(content) = fs::read_to_string(rule_path) {
                            if let Ok(rules_val) = serde_json::from_str::<Value>(&content) {
                                if let Some(groups) = rules_val.as_array() {
                                    for group in groups {
                                        let params = &group["params"];

                                        // param checks: TIME_FROM_CREATION_MINUTES, NOWSOL_RANGE, TRADE_AMOUNT_RANGE,
                                        // FILTERED_TRADES_MIN_AMOUNT, FILTERED_TRADES_COUNT, FILTERED_TRADES_SUM_RANGE
                                        let mut params_ok = true;

                                        if let Some(min_minutes) = params.get("TIME_FROM_CREATION_MINUTES").and_then(|v| v.as_i64()) {
                                            let elapsed_min = ((*data.trade_miltime() as i64 - watcher.start_time as i64) / 60000) as i64;
                                            if elapsed_min < min_minutes {
                                                params_ok = false;
                                            }
                                        }

                                        if params_ok {
                                            if let Some(nr) = params.get("NOWSOL_RANGE").and_then(|v| v.as_array()) {
                                                if nr.len() >= 2 {
                                                    if let (Some(nmin), Some(nmax)) = (nr[0].as_f64(), nr[1].as_f64()) {
                                                        let nowsol = *data.post_sol_amount() as f64;
                                                        if !(nmin <= nowsol && nowsol <= nmax) {
                                                            params_ok = false;
                                                        }
                                                    }
                                                }
                                            }
                                        }

                                        if params_ok {
                                            if let Some(tr) = params.get("TRADE_AMOUNT_RANGE").and_then(|v| v.as_array()) {
                                                if tr.len() >= 2 {
                                                    if let (Some(tmin), Some(tmax)) = (tr[0].as_f64(), tr[1].as_f64()) {
                                                        let amt = *data.trade_sol_amount() as f64;
                                                        if !(tmin <= amt && amt <= tmax) {
                                                            params_ok = false;
                                                        }
                                                    }
                                                }
                                            }
                                        }

                                        // filtered trades sum
                                        if params_ok {
                                            if let (Some(min_amount_v), Some(count_v), Some(sum_range_v)) = (
                                                params.get("FILTERED_TRADES_MIN_AMOUNT"),
                                                params.get("FILTERED_TRADES_COUNT"),
                                                params.get("FILTERED_TRADES_SUM_RANGE"),
                                            ) {
                                                if let (Some(min_amount), Some(count)) = (min_amount_v.as_f64(), count_v.as_u64()) {
                                                    // compute sum of last `count` trades with abs(amount)>=min_amount
                                                    // buy_amount is always positive; apply sign from trade_type to match Python tradeamount
                                                    let mut c = 0usize;
                                                    let mut ssum = 0.0f64;
                                                    for rt in recent_trades.iter() {
                                                        let raw_amt = rt.buy_amount as f64;
                                                        let signed_amt = if rt.trade_type.as_str() == "sell" { -raw_amt } else { raw_amt };
                                                        if raw_amt >= min_amount {
                                                            ssum += signed_amt;
                                                            c += 1;
                                                            if c >= count as usize {
                                                                break;
                                                            }
                                                        }
                                                    }
                                                    if c < count as usize {
                                                        params_ok = false;
                                                    } else if let Some(sum_range) = sum_range_v.as_array() {
                                                        if sum_range.len() >= 2 {
                                                            if let (Some(smin), Some(smax)) = (sum_range[0].as_f64(), sum_range[1].as_f64()) {
                                                                if !(smin <= ssum && ssum <= smax) {
                                                                    params_ok = false;
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }

                                        if !params_ok {
                                            continue;
                                        }

                                        // params matched -> candidate group
                                        matched_group = Some(group);

                                        // now evaluate conditions: for each condition, compute metric and test buckets
                                        if let Some(conds) = group.get("conditions").and_then(|v| v.as_array()) {
                                            let empty_buckets = vec![];
                                            for cond in conds.iter() {
                                                let cond_name = cond.get("condition").and_then(|v| v.as_str()).unwrap_or("");
                                                let buckets = cond.get("buckets").and_then(|v| v.as_array()).unwrap_or(&empty_buckets);

                                                // Helper: compute coefficient of variation (std / |mean|)
                                                let compute_cv = |vals: &[f64]| -> Option<f64> {
                                                    if vals.len() < 2 { return None; }
                                                    let mean = vals.iter().sum::<f64>() / vals.len() as f64;
                                                    if mean.abs() < 1e-12 { return Some(0.0); }
                                                    let var = vals.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / vals.len() as f64;
                                                    Some(var.sqrt() / mean.abs())
                                                };

                                                // compute metric value for this condition
                                                let metric: Option<f64> = match cond_name {
                                                    "TIME_DIFF" => {
                                                        // time diff (ms) from the most recent trade
                                                        if let Some(rt0) = recent_trades.get(0) {
                                                            Some((*data.trade_miltime() as f64) - (rt0.swap_time as f64))
                                                        } else {
                                                            None
                                                        }
                                                    }
                                                    "PRICE_VOLATILITY" => {
                                                        // Use post_sol_amount as price proxy (PrepareTradeMetrics has no price field)
                                                        let prices: Vec<f64> = recent_trades.iter()
                                                            .map(|rt| rt.post_sol_amount as f64)
                                                            .filter(|p| *p > 0.0)
                                                            .collect();
                                                        compute_cv(&prices)
                                                    }
                                                    "TIME_VOLATILITY" => {
                                                        // CV of time intervals between consecutive trades
                                                        let mut intervals: Vec<f64> = Vec::new();
                                                        let mut prev_time: Option<u128> = None;
                                                        for rt in recent_trades.iter() {
                                                            let t = rt.swap_time;
                                                            if let Some(pv) = prev_time {
                                                                let diff = (pv as f64) - (t as f64);
                                                                if diff.abs() > 0.0 {
                                                                    intervals.push(diff);
                                                                }
                                                            }
                                                            prev_time = Some(t);
                                                        }
                                                        compute_cv(&intervals)
                                                    }
                                                    "AMOUNT_VOLATILITY" => {
                                                        let amts: Vec<f64> = recent_trades.iter()
                                                            .map(|rt| rt.buy_amount as f64)
                                                            .collect();
                                                        compute_cv(&amts)
                                                    }
                                                    "PRICE_RATIO" => {
                                                        // ratio of current price to min recent price (%)
                                                        // Use post_sol_amount as price proxy
                                                        let current_price = *data.post_sol_amount() as f64;
                                                        let prices: Vec<f64> = recent_trades.iter()
                                                            .map(|rt| rt.post_sol_amount as f64)
                                                            .filter(|p| *p > 0.0)
                                                            .collect();
                                                        if !prices.is_empty() {
                                                            let minp = prices.iter().cloned().fold(f64::INFINITY, f64::min);
                                                            if minp > 0.0 { Some((current_price / minp - 1.0) * 100.0) } else { None }
                                                        } else { None }
                                                    }
                                                    "BUY_COUNT" => {
                                                        let bc = recent_trades.iter()
                                                            .filter(|rt| rt.trade_type.as_str() == "buy")
                                                            .count();
                                                        Some(bc as f64)
                                                    }
                                                    "SELL_COUNT" => {
                                                        let sc = recent_trades.iter()
                                                            .filter(|rt| rt.trade_type.as_str() == "sell")
                                                            .count();
                                                        Some(sc as f64)
                                                    }
                                                    "LARGE_TRADE_RATIO" => {
                                                        let large_threshold = params.get("LARGE_TRADE_THRESHOLD").and_then(|v| v.as_f64()).unwrap_or(1.0);
                                                        let total = recent_trades.len();
                                                        if total == 0 { None } else {
                                                            let large = recent_trades.iter()
                                                                .filter(|rt| (rt.buy_amount as f64) >= large_threshold)
                                                                .count();
                                                            Some(large as f64 / total as f64)
                                                        }
                                                    }
                                                    "SMALL_TRADE_RATIO" => {
                                                        let small_threshold = params.get("SMALL_TRADE_THRESHOLD").and_then(|v| v.as_f64()).unwrap_or(0.1);
                                                        let total = recent_trades.len();
                                                        if total == 0 { None } else {
                                                            let small = recent_trades.iter()
                                                                .filter(|rt| (rt.buy_amount as f64) < small_threshold)
                                                                .count();
                                                            Some(small as f64 / total as f64)
                                                        }
                                                    }
                                                    "CONSECUTIVE_BUY" => {
                                                        let cnt = recent_trades.iter()
                                                            .take_while(|rt| rt.trade_type.as_str() == "buy")
                                                            .count();
                                                        Some(cnt as f64)
                                                    }
                                                    "CONSECUTIVE_SELL" => {
                                                        let cnt = recent_trades.iter()
                                                            .take_while(|rt| rt.trade_type.as_str() == "sell")
                                                            .count();
                                                        Some(cnt as f64)
                                                    }
                                                    _ => None,
                                                };

                                                if let Some(metric_val) = metric {
                                                    for bs in buckets.iter() {
                                                        let low = bs.get("low").and_then(|v| v.as_f64());
                                                        let high = bs.get("high").and_then(|v| v.as_f64());
                                                        if let (Some(lo), Some(hi)) = (low, high) {
                                                            // treat 1e9 as +infinity (rule.json uses 1e9 for unbounded)
                                                            let effective_hi = if hi >= 1e8 { f64::INFINITY } else { hi };
                                                            if metric_val >= lo && metric_val < effective_hi {
                                                                let avg_pr = bs.get("avg_profit_rate").and_then(|v| v.as_f64()).unwrap_or(0.0);
                                                                matched_bucket_avg_profit = Some(avg_pr);
                                                                break;
                                                            }
                                                        }
                                                    }
                                                }

                                                if matched_bucket_avg_profit.is_some() {
                                                    break;
                                                }
                                            }
                                        }

                                        if matched_bucket_avg_profit.is_some() {
                                            break;
                                        }
                                    }
                                }
                            }
                        }
                    }

                    if let Some(avg_pr) = matched_bucket_avg_profit {
                        let base_buy_sol = 0.2f64;
                        let weight = 5.0f64;
                        let bonus = base_buy_sol * (avg_pr.max(0.0).min(0.1)) * weight;
                        let buy_sol = base_buy_sol + bonus;

                        let mut trade_token_amount = (*data.trade_token_amount() as f64 * buy_sol * 1e-6)
                            / (*data.trade_sol_amount() as f64);
                        if trade_token_amount < 1000.0 {
                            trade_token_amount = trade_token_amount * 1e6;
                        }

                        if MINT_CACHE2.entry_count() <= 20 {
                            UNIFY_BUY_CHANNEL
                                .sender
                                .send(TradeMessage::AmountMessage(
                                    data.clone(),
                                    trade_token_amount,
                                    watcher.timestamp,
                                    watcher.max_open_time,
                                ))
                                .unwrap();

                            tracing::info!("[规则买入] 基于avg_pr={:.4}，买入SOL={}，token_amount={}", avg_pr, buy_sol, trade_token_amount);
                            watcher.mint_status = MintStatus::IsBuying;
                            watcher.start_price = *data.price();
                            watcher.start_post_sol = *data.post_sol_amount();
                            watcher.open_time = *data.trade_miltime();
                        } else {
                            tracing::warn!("[规则买入] 超出持仓限制，无法买入: {}", data.trade_mint());
                        }
                    }

                    let mut can_buy = false;

                    if can_buy {
                        let (sell_min_price, sell_max_price) = lianghua_watch
                            .price_history
                            .iter()
                            .skip(1)
                            .take(10)
                            .fold((f64::MAX, f64::MIN), |(min, max), info| {
                                (min.min(*info), max.max(*info))
                            });

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

                        tracing::warn!(
                            "[{}] {},命中买入，时间{} ! 当前 {} 交易金额 {} 价格 {} 开始价格 {} https://gmgn.ai/sol/token/{}",
                            data.trade_mint(),_beijing_time,data.trade_miltime().saturating_sub(watcher.start_time), data.user(), data.trade_sol_amount(), data.price(), watcher.start_price, data.trade_mint(),
                        );

                        watcher.group_full_name = format!(
                            "{}-{}",
                            data.trade_type(),
                            data.trade_mint(),
                        );

                        watcher.max_open_time = 2 * 60 * 1000;
                        watcher.start_sol = *data.trade_sol_amount();
                        watcher.is_fake_trade = false;

                        let record = GROUP_CACHE.get(&watcher.group_full_name.clone());
                        if let Some(rd) = record {
                            let fail_cnt = rd
                                .group_max_rate_record
                                .iter()
                                .take(4)
                                .filter(|&&rate| rate < -15.0)
                                .count();

                            let succ_cnt = rd
                                .group_max_rate_record
                                .iter()
                                .take(7)
                                .filter(|&&rate| rate > 5.0)
                                .count();

                            let succ_cnt2 = rd
                                .group_max_rate_record
                                .iter()
                                .take(15)
                                .filter(|&&rate| rate > 5.0)
                                .count();

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
                        record
                            .group_buyed_mint
                            .push_front(data.trade_mint().to_string());
                    }

                    watcher.mint_status = MintStatus::IsBuyed;
                    watcher.buy_sol_amount = *data.trade_sol_amount();
                    watcher.open_time = *data.trade_miltime();
                    watcher.final_hit_buy_user = *data.user();
                    watcher.final_hit_buy_time =
                        data.trade_miltime().saturating_sub(watcher.timestamp);
                    watcher.final_hit_buy_price = *data.price();
                    watcher.max_open_time = 2 * 60 * 1000; // 2分钟
                } else if watcher.is_fake_trade
                    && (*data.trade_miltime() < watcher.timestamp + 120
                        || *data.trade_miltime() > watcher.timestamp + 1000)
                {
                    watcher.start_price = *data.price();
                    watcher.start_post_sol = *data.post_sol_amount();
                } else if !watcher.is_fake_trade && !watcher.is_test_trade {
                    let mut rate = 1.0;
                    let global_group_full_name = "quant_global_group".to_string();
                    if let Some(group_record) = GROUP_CACHE.get(&global_group_full_name) {
                        let recent_win_5 = group_record
                            .group_max_rate_record
                            .iter()
                            .take(5)
                            .filter(|&&rate| rate > 4.0)
                            .count();

                        let recent_big_win_5 = group_record
                            .group_max_rate_record
                            .iter()
                            .take(5)
                            .filter(|&&rate| rate > 10.0)
                            .count();

                        if recent_big_win_5 >= 2 {
                            rate = 3.0;
                        } else if recent_win_5 > 2 {
                            rate = 2.0;
                        }
                    }

                    let mut buyed_sol = 0.36;
                    rate = 1.0;
                    let beijing_hour =
                        chrono::NaiveDateTime::from_timestamp_opt(*data.trade_time() as i64, 0)
                            .map(|t| (t + chrono::Duration::hours(8)).hour())
                            .unwrap_or(0);
                    if beijing_hour >= 0 && beijing_hour < 7 {
                        buyed_sol = 0.25 * rate;
                    } else {
                        buyed_sol = 0.2 * rate;
                    }
                    let mut buyed_sol = 0.4;

                    let mut trade_token_amount =
                        (*data.trade_token_amount() as f64 * buyed_sol * 1e-6)
                            / (*data.trade_sol_amount() as f64);

                    if trade_token_amount < 1000.0 {
                        trade_token_amount = trade_token_amount * 1e6;
                    }

                    if MINT_CACHE2.entry_count() <= 20 {
                        UNIFY_BUY_CHANNEL
                            .sender
                            .send(TradeMessage::AmountMessage(
                                data.clone(),
                                trade_token_amount,
                                watcher.timestamp,
                                watcher.max_open_time,
                            ))
                            .unwrap();
                        tracing::info!(
                            "[正式买入] 当前 {} 允许直接买入, 交易金额：{} https://gmgn.ai/sol/token/{}",
                            watcher.group_full_name,
                            data.trade_sol_amount(),
                            data.trade_mint()
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
