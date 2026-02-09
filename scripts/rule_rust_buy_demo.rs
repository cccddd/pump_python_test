use std::f32::consts::E;

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
use tokio::sync::watch;

pub struct QtfyNewStrategyDemo;


#[async_trait]
impl PipelineHandler for QtfyNewStrategyDemo {
    async fn handle(&self, data: TradeContextNew) -> Option<TradeContextNew> {
        let _need_remove = false;

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
                        && data.trade_type() == "sell"; //&& lianghua_watch.cur_swap_time-lianghua_watch.last_swap_time > 20*1000;

                    let recent_trades: Vec<_> = lianghua_watch
                            .prepareTrade
                            .iter()
                            .take(200)
                            .collect();
                    

                    let mut can_buy = false;

                    if can_buy {
                        {
                            //time_ok && pool_ok && is_breakout && volume_ok && freq_ok {
                            // 命中买入信号 -> 标记为 CanBuy 并记录初始信息

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
                                // watcher.create_compute_price,
                                data.trade_mint(),
                                // watcher.create_limit
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
                                
                                //println!("succ_cnt:{} fail_cnt:{}", succ_cnt, fail_cnt);
                            }
                            // else {
                            //     watcher.is_fake_trade = true;
                            // }
                            if watcher.is_test_trade {
                                watcher.is_fake_trade = true;
                            } 
                            else {
                                watcher.sell_level = 1;
                            }
                            // else {
                            //     watcher.is_fake_trade = false;
                            // }
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
                    // if watcher.is_test_trade {
                    //     let buy_snapshot = BuySnapshot {
                    //         post_sol: *data.post_sol_amount(),
                    //         open_time_stamp: *data.trade_miltime() - watcher.start_time,
                    //         buy_reason: "test_trade".into(),
                    //         trade_sol: *data.trade_sol_amount(),
                    //         buy_price: *data.price(),
                    //         last_trade_time: lianghua_watch.last_swap_time,
                    //         compute_unit_price: *data.compute_unit_price(),
                    //         swap_trade_buy_cnt: succ_cnt,
                    //         swap_trade_sell_cnt: loss_cnt,
                    //         total_swap_sol: total_sol_15,
                    //         cv: 0.0,
                    //     };
                    //     watcher.buy_snapshot = Some(buy_snapshot);
                    // }

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

                    let mut buyed_sol = 0.36; // * rate;
                    rate = 1.0;
                    //如果是北京时间0-7点，buyed_sol增加为0.33，否则设置为0.2
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
