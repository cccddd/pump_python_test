

将scripts/rules/rule1_optimize.py variant_find_buy_signal方法涉及到的交易特征，需要也通过rust代码进行实现，并且支持从rules.json里提取买入条件的规则。当满足params的条件时（mode=online或者前面的几个条件）时，设置can_buy=true，当当前单子满足condition（即命中了对应的分桶时），买入金额随着盈利率增加而叠加（具体算法你需要通过几个值进行加权）

对于rust代码，我提供了部分字段解释，你需要参考
lianghua_watch.prepareTrade 当接受到一条交易信息时，会将该交易通过push_front塞入到 lianghua_watch.prepareTrade

具体代码参考：
lianghua_watch.prepareTrade.push_front(prepareTradeMetrics); 

#[derive(Debug, Default, Clone)]
#[allow(dead_code)]
pub struct PrepareTradeMetrics {
    pub mint: String,
    pub swap_time: u128,//交易时间，单位毫秒，等同于mint_temp.log里的字段tradetime
    pub trade_type: String,         // buy or sell
    pub buy_amount: f32,            //交易金额都为正，等同于 mint_temp.log里的tradeamount 
    pub post_sol_amount: f32,       //当前市值，等同mint_temp.log里的字段nowsol
}

