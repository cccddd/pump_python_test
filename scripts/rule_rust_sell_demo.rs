use crate::{
    context::{self, context::TradeContextNew, context_new::MintStatus, trader::TradeMessage},
    help::{
        global::{global_struct, UNIFY_SELL_CHANNEL, WATCH_CACHE}, global_xd::xd_global_struct, tool::get_current_milsec
    },
    processer::PipelineHandler,
};
use async_trait::async_trait;
use std::io::Write; // for writeln! to resolve write_fmt on File

/// 量化卖出策略
pub struct  PumpQtfySellProcesserDemo;

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

            let mut sell_reason = "".to_string();
            let beijing_time =
                        chrono::NaiveDateTime::from_timestamp_opt(*data.trade_time() as i64, 0)
                            .map(|t| {
                                (t + chrono::Duration::hours(8))
                                    .format("%Y-%m-%d %H:%M:%S")
                                    .to_string()
                            })
                            .unwrap_or_else(|| "Invalid timestamp".to_string());
            
          
                //重写触发价格和时间
                if indicator.swap_cnt<1{
                    indicator.start_price=data.price().clone();
                    indicator.open_time = data.trade_miltime().clone();
                    indicator.rate=0.0;
                    indicator.max_rate=0.0;
                    indicator.min_rate=0.0;
                    indicator.max_price=0.0;
                    indicator.min_price=0.0;
                    // return Some(data);
                }
                let key = data.trade_mint().to_string();
            if let Some(mut watching_feed) = xd_global_struct
                .watching_bsc_mint_feed_info
                .get_mut(key.as_str())
            {
                let feed = watching_feed.value_mut();
                if feed.is_black_source>0{
                    need_sell=true;
                    sell_reason += format!("命中拉黑卖出  ,拉黑类型 {} |",feed.is_black_source.clone()).as_str();
                }

            

                let current=data.trade_miltime().clone();
                let open_last_time = current.saturating_sub(indicator.open_time);

                let rate;
                if *data.price() != 0.0 {
                    rate = 100.0 * (*data.price() / indicator.start_price - 1.0);
                    if rate < -60.0 {
                        indicator.rate = 0.0;
                        return Some(data);
                    }
                    indicator.rate = rate;
                } else {
                    rate = indicator.rate;
                }
                indicator.max_rate = indicator.max_rate.max(rate);
                if data.trade_type() == "buy" {
                    if *data.trade_sol_amount() > 0.4 {
                        indicator.big_buy_cnt += 1;
                    } else {
                        indicator.small_buy_cnt += 1;
                    }
                }

                if data.trade_type() == "sell"  {
                    if *data.trade_sol_amount() > 1.0 {
                        indicator.big_sell_cnt += 1;
                    } else {
                        indicator.small_sell_cnt += 1;
                    }
                }
               if *data.price() > indicator.max_price {
                        indicator.max_price = *data.price();
                }
                if *data.price() < indicator.min_price || indicator.min_price == 0.0 {
                        indicator.min_price = *data.price();
                }

                indicator.swap_cnt+=1;
                //回撤
                let drawdown_rate= (indicator.max_price - *data.price())/indicator.max_price*100.0;

                //反弹比例
                let rebound_rate= (*data.price() - indicator.min_price)/indicator.min_price*100.0;
                //


                if indicator.min_price!=*data.price()  &&  drawdown_rate >3.0 && data.trade_type()=="sell"  {
                    sell_reason += format!("回撤超过3% {:.2}%|",drawdown_rate).as_str();
                    need_sell = true;
                }

                if indicator.rate < -3.0 && (*data.price() < indicator.sell_min_price && indicator.sell_min_price>0.0 )  {
                        sell_reason += format!("亏损3% {:.2}%|", indicator.rate).as_str();
                        need_sell = true;
                }
                if indicator.big_sell_cnt>=2  &&  drawdown_rate >3.0 && data.trade_type()=="sell"  {
                    sell_reason += format!("回撤超过3% {:.2}%|",drawdown_rate).as_str();
                    need_sell = true;
                }

                if indicator.swap_cnt>=10  && indicator.max_rate<10.0 && drawdown_rate >2.0 && data.trade_type()=="sell"  {
                    sell_reason += format!("回撤超过2% {:.2}%|",drawdown_rate).as_str();
                    need_sell = true;
                }

                if data.trade_miltime().saturating_sub(indicator.start_time)<3*1000{
                    if indicator.big_buy_cnt>2 && indicator.rate>15.0{
                        sell_reason += format!("短周期卖单% {:.2}%|",indicator.rate).as_str();
                        need_sell = true;
                    }
                }





                //止盈逻辑
                // if rebound_rate > 130.0 && data.trade_type() == "sell" {
                //     sell_reason += format!("反弹超过130% {:.2}%|", rebound_rate).as_str();
                //     need_sell = true;
                // }


                if *data.post_sol_amount()>70.0  {
                    sell_reason += format!("高市值70 {:.2}%|", *data.post_sol_amount()).as_str();
                    need_sell = true;
                }

            //    if *data.trade_sol_amount() < 1.5  &&  (indicator.big_sell_cnt<2 && indicator.small_sell_cnt<3)  {
            //         need_sell = false;
            //     }


                if need_sell && indicator.mint_status == MintStatus::IsBuyed {
                    // build detailed diagnostic info for logging
                    let recent_rates = 0.0;

                    let delta_max = indicator.max_rate - indicator.rate;
                    let sell_reason_details = format!(
                        "reason_tags={} | rate={:.2}% | max_rate={:.2}% | delta={:.2}% | open_last_time={}ms | swap_cnt={} | big_buy_cnt={} | small_buy_cnt={} | big_sell_cnt={} | small_sell_cnt={} | continous_sell_cnt={} | continous_buy_cnt={} | sell_max_price={:.6} | sell_min_price={:.6} | last_big_buy_time={} | recent_rates=[{}]",
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
                        recent_rates
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
                                *data.trade_sol_amount()
                                ,indicator.big_buy_cnt
                                ,indicator.small_buy_cnt
                                ,indicator.big_sell_cnt
                                ,indicator.small_sell_cnt
                            );

                    if !indicator.is_fake_trade {
                        indicator.my_sell_time=*data.trade_miltime();
                        UNIFY_SELL_CHANNEL
                            .sender
                            .send(TradeMessage::AmountMessage(data.clone(), 0.2, 0, 0))
                            .unwrap();
                        indicator.mint_status = MintStatus::IsSelling;
                    } else {

                            if indicator.my_sell_time==0{
                                indicator.my_sell_time=*data.trade_miltime();
                            }



                            indicator.mint_status = MintStatus::IsSelling;
                            //判断是否存在indicator.buy_snapshot，存在则把买入快照信息打印出来，另外把当前的卖出数据，也打印出来
                            if let Some(buy_snapshot) = &indicator.buy_snapshot {
                                // pub post_sol: f32,//当前市值
                                // pub open_time_stamp: u128,//距离开始时间
                                // pub buy_reason: String,//买入理由
                                // pub trade_sol: f32,//买入金额
                                // pub buy_price: f64,//买入价格
                                // pub last_trade_time: u128,//距离上一交易时间
                                // pub compute_unit_price: u64,//买点触发特征
                                // pub swap_trade_buy_cnt: usize,//近期买单次数
                                // pub swap_trade_sell_cnt: usize,//近期卖单次数
                                // pub total_swap_sol: f32,//近期总交易量
                                // pub cv: f64,//近期交易量波动率
                                let log_msg=format!(
                                    "买入快照信息,交易币种:{} 开仓时间戳:{}，买入价格:{}，买入金额:{}，买入理由:{}，买入后市值:{}，买入时计算单价:{}，买入时买单次数:{}，买入时卖单次数:{}，买入时总交易量:{}，买入时交易量波动率:{};卖出时信息： 当前价格:{}，当前涨幅:{}，最大涨幅:{}，大单数量:{}，小单数量:{}，卖单数量:{}，小卖单数量:{} ",
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
                                    indicator.small_sell_cnt
                                );
                                // 将 log_msg 写到日志文件0113.log（确保文件存在并捕获错误，避免 unwrap 导致 panic）

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





                            // if indicator.buy_snapshot {

                            // }

                            // tracing::warn!(
                            //     "[{}]{} {},卖出滑点300毫秒，{} {} {} , 价格{}]>{},比例{}=>{},大单数量{},小单数量{},卖单数量{},小卖单数量{} ",
                            //     data.trade_mint().to_string(),
                            //     beijing_time,
                            //     open_last_time,
                            //     data.user(),
                            //     data.trade_type(),
                            //     data.trade_sol_amount(),
                            //     data.price(),
                            //     indicator.hit_price,
                            //     indicator.rate,
                            //     indicator.max_rate,
                            //     indicator.big_buy_cnt,
                            //     indicator.small_buy_cnt,
                            //     indicator.big_sell_cnt,
                            //     indicator.small_sell_cnt
                            // );

                    }
                    if rate > 0.0 {
                        indicator.win_last_time = open_last_time;
                    } else {
                        indicator.loss_last_time = open_last_time;
                    }
                    indicator.open_last_time = open_last_time;
                    indicator.end_post_sol = *data.post_sol_amount();
                    indicator.close_time = current;
                    indicator.is_selling = true;
                    if indicator.is_fake_trade {
                        indicator.is_selled = true;
                    }
                    indicator.last_swap_time=data.trade_miltime().clone();
                }
}
             if  (indicator.is_fake_trade && indicator.mint_status == MintStatus::IsSelling ){
                let self_wallets = vec![
                // "4VRpAHcpW6CrpLdxrBYkH6w959Zntnzyt4vfaFr56RKK".to_string(),
                // "GNr8d4mYvxTSR48JZNPaTqjUB2Wb3Hp7MPpYy11AX8hS".to_string(),
                // "GuKBpnQhP27JEP3QNna1jKLMeMRvZnqCxMAsPDso6Xvt".to_string(),
                // "9anmiHy6TQsoeLdBty2EExZqUYiKYeWSjaRoznRBCu5G".to_string(),
                // "D4ki5hVvjvuMmHyjX62rzzzkAfQycShwUKtQFouFbkCE".to_string(),
                "4WEbzvm5RzSnBB5jWbXoTyRg4RFkkX5XmEf2UxR4LcDR".to_string(),
            ];

                if self_wallets.contains(&data.user().to_string() )|| data.user().to_string() == "4VRpAHcpW6CrpLdxrBYkH6w959Zntnzyt4vfaFr56RKK".to_string()|| *data.post_sol_amount() < 1.5 || (indicator.my_sell_time > 0 &&  *data.trade_miltime()>indicator.my_sell_time+100){
                            indicator.mint_status = MintStatus::IsSelled;
                            // if  self_wallets.contains(&data.user().to_string() ) && indicator.buy_sol_amount>0.0{
                            //     let sell_sol_amount=*data.trade_sol_amount();
                            //     indicator.rate=(sell_sol_amount/indicator.buy_sol_amount*100.0-100.0) as f64;
                            // }
                            indicator.real_sell_price=*data.price();
                            indicator.real_sell_time=*data.trade_miltime();
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

                }else{
                    let rate1 = 100.0 * (*data.price() / indicator.start_price - 1.0);
                    indicator.rate = rate1;
                    indicator.hit_price=*data.price();
                    // indicator.my_sell_time=*data.trade_miltime();
                }

            }
        }

        return Some(data);
    }
}