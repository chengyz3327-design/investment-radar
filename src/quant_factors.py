"""
量化因子分析模块 - 基于诺贝尔经济学奖获奖理论
Fama-French 多因子模型 / Black-Scholes 波动率 / Markowitz 风险度量
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class QuantFactorEngine:
    """量化因子分析引擎"""

    # 无风险年化利率（10年期国债收益率近似）
    RISK_FREE_RATE = 0.025

    def analyze(self, daily_df: Optional[pd.DataFrame], financial: Optional[Dict],
                price_info: Optional[Dict]) -> Dict[str, Any]:
        """综合因子分析，返回全部因子数据"""
        result = {
            "model_version": "v2.1-academic",
            "factors": {},
            "risk_metrics": {},
            "momentum": {},
            "smart_money": {},
            "overall_quant_score": 0,
            "quant_level": "",
        }

        if daily_df is not None and len(daily_df) > 20:
            closes = daily_df['close'].astype(float)
            highs = daily_df['high'].astype(float)
            lows = daily_df['low'].astype(float)
            volumes = daily_df['volume'].astype(float)
            returns = closes.pct_change().dropna()

            result["factors"] = self._calc_fama_french_factors(returns, closes, financial)
            result["risk_metrics"] = self._calc_risk_metrics(returns, closes)
            result["momentum"] = self._calc_momentum(closes, returns, volumes)
            result["smart_money"] = self._calc_smart_money(closes, highs, lows, volumes)

            # 输出最近60日收盘价用于前端迷你走势图
            result["_price_series"] = closes.tail(60).tolist()

        score = self._calc_quant_score(result)
        result["overall_quant_score"] = score
        result["quant_level"] = self._score_to_level(score)

        return result

    # ================================================================
    #  Fama-French 因子 (诺贝尔经济学奖 2013)
    # ================================================================

    def _calc_fama_french_factors(self, returns: pd.Series, closes: pd.Series,
                                  financial: Optional[Dict]) -> Dict[str, Any]:
        """
        Fama-French 五因子模型指标
        Mkt-RF / SMB / HML / RMW / CMA
        """
        ann_return = float(returns.mean() * 252)
        ann_vol = float(returns.std() * np.sqrt(252))

        # Beta (市场因子 Mkt-RF)：用收益率自相关近似
        if len(returns) > 5:
            beta = float(np.corrcoef(returns.iloc[:-1], returns.iloc[1:])[0, 1] * 1.2 + 0.8)
            beta = round(max(0.3, min(2.5, beta)), 3)
        else:
            beta = 1.0

        # Alpha (Jensen's Alpha)
        market_return = 0.08  # 市场年化假设
        alpha = ann_return - self.RISK_FREE_RATE - beta * (market_return - self.RISK_FREE_RATE)
        alpha = round(alpha, 4)

        # HML (价值因子) - 用PB/ROE近似
        hml_score = 0.0
        if financial:
            roe = financial.get("roe", 0)
            debt = financial.get("debt_ratio", 50)
            if roe > 15:
                hml_score = 0.6
            elif roe > 8:
                hml_score = 0.3
            elif roe > 0:
                hml_score = 0.0
            else:
                hml_score = -0.4
            if debt > 75:
                hml_score -= 0.2

        # RMW (盈利因子)
        rmw_score = 0.0
        if financial:
            net_profit_yoy = financial.get("net_profit_yoy", 0)
            if net_profit_yoy > 20:
                rmw_score = 0.5
            elif net_profit_yoy > 0:
                rmw_score = 0.2
            elif net_profit_yoy > -20:
                rmw_score = -0.1
            else:
                rmw_score = -0.5

        # CMA (投资因子)
        cma_score = round(hml_score * 0.6 + rmw_score * 0.4, 3)

        return {
            "model": "Fama-French 五因子",
            "nobel_year": 2013,
            "beta": beta,
            "alpha": alpha,
            "annual_return": round(ann_return, 4),
            "annual_volatility": round(ann_vol, 4),
            "hml_value": round(hml_score, 3),
            "rmw_profitability": round(rmw_score, 3),
            "cma_investment": cma_score,
        }

    # ================================================================
    #  风险度量 (Markowitz 诺贝尔 1990 / Black-Scholes 1997)
    # ================================================================

    def _calc_risk_metrics(self, returns: pd.Series, closes: pd.Series) -> Dict[str, Any]:
        """
        Markowitz 现代投资组合理论风险指标
        VaR / CVaR / 最大回撤 / Sharpe / Sortino / Calmar
        """
        ann_return = float(returns.mean() * 252)
        ann_vol = float(returns.std() * np.sqrt(252))

        # Sharpe Ratio (William Sharpe, 诺贝尔 1990)
        sharpe = (ann_return - self.RISK_FREE_RATE) / ann_vol if ann_vol > 0 else 0

        # Sortino Ratio（只看下行波动率）
        downside = returns[returns < 0]
        downside_vol = float(downside.std() * np.sqrt(252)) if len(downside) > 0 else ann_vol
        sortino = (ann_return - self.RISK_FREE_RATE) / downside_vol if downside_vol > 0 else 0

        # VaR (95%) - 参数法
        var_95 = float(returns.mean() - 1.645 * returns.std())

        # CVaR (Expected Shortfall)
        threshold = returns.quantile(0.05)
        tail = returns[returns <= threshold]
        cvar_95 = float(tail.mean()) if len(tail) > 0 else var_95

        # Maximum Drawdown
        cummax = closes.cummax()
        drawdown = (closes - cummax) / cummax
        max_drawdown = float(drawdown.min())

        # Calmar Ratio
        calmar = ann_return / abs(max_drawdown) if max_drawdown != 0 else 0

        # 波动率锥（近期 vs 长期）
        vol_20d = float(returns.tail(20).std() * np.sqrt(252)) if len(returns) >= 20 else ann_vol
        vol_60d = float(returns.tail(60).std() * np.sqrt(252)) if len(returns) >= 60 else ann_vol

        return {
            "model": "Markowitz-Sharpe 风险度量",
            "nobel_year": 1990,
            "sharpe_ratio": round(sharpe, 3),
            "sortino_ratio": round(sortino, 3),
            "calmar_ratio": round(calmar, 3),
            "var_95": round(var_95 * 100, 2),
            "cvar_95": round(cvar_95 * 100, 2),
            "max_drawdown": round(max_drawdown * 100, 2),
            "volatility_20d": round(vol_20d * 100, 2),
            "volatility_60d": round(vol_60d * 100, 2),
            "volatility_annual": round(ann_vol * 100, 2),
        }

    # ================================================================
    #  动量因子 (Jegadeesh & Titman / AQR)
    # ================================================================

    def _calc_momentum(self, closes: pd.Series, returns: pd.Series,
                       volumes: pd.Series) -> Dict[str, Any]:
        n = len(closes)
        # 各周期动量
        mom_5d = float((closes.iloc[-1] / closes.iloc[-6] - 1)) if n >= 6 else 0
        mom_20d = float((closes.iloc[-1] / closes.iloc[-21] - 1)) if n >= 21 else 0
        mom_60d = float((closes.iloc[-1] / closes.iloc[-61] - 1)) if n >= 61 else 0
        mom_120d = float((closes.iloc[-1] / closes.iloc[-121] - 1)) if n >= 121 else 0

        # RSI (14日)
        delta = closes.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - 100 / (1 + rs)
        rsi_val = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50

        # 量价背离检测
        price_trend = mom_20d
        vol_ma5 = float(volumes.tail(5).mean())
        vol_ma20 = float(volumes.tail(20).mean()) if n >= 20 else vol_ma5
        vol_ratio = vol_ma5 / vol_ma20 if vol_ma20 > 0 else 1.0
        divergence = "无" 
        if price_trend > 0.03 and vol_ratio < 0.7:
            divergence = "价升量缩（顶背离信号）"
        elif price_trend < -0.03 and vol_ratio > 1.3:
            divergence = "价跌量增（恐慌抛售）"
        elif price_trend < -0.03 and vol_ratio < 0.7:
            divergence = "缩量下跌（底部企稳）"

        return {
            "model": "Cross-Sectional Momentum",
            "momentum_5d": round(mom_5d * 100, 2),
            "momentum_20d": round(mom_20d * 100, 2),
            "momentum_60d": round(mom_60d * 100, 2),
            "momentum_120d": round(mom_120d * 100, 2),
            "rsi_14": round(rsi_val, 1),
            "volume_ratio": round(vol_ratio, 2),
            "divergence_signal": divergence,
        }

    # ================================================================
    #  聪明钱指标 (Smart Money Flow)
    # ================================================================

    def _calc_smart_money(self, closes: pd.Series, highs: pd.Series,
                          lows: pd.Series, volumes: pd.Series) -> Dict[str, Any]:
        """Chaikin Money Flow / OBV 聪明钱流向"""
        n = len(closes)
        if n < 20:
            return {"model": "Smart Money Flow", "cmf_20": 0, "obv_trend": "数据不足"}

        # CMF (Chaikin Money Flow 20日)
        mfv = ((2 * closes - lows - highs) / (highs - lows).replace(0, np.nan)) * volumes
        mfv = mfv.fillna(0)
        cmf = float(mfv.tail(20).sum() / volumes.tail(20).sum()) if volumes.tail(20).sum() > 0 else 0

        # OBV 趋势
        obv = (np.sign(closes.diff()) * volumes).fillna(0).cumsum()
        obv_ma = obv.rolling(20).mean()
        obv_trend = "中性"
        if len(obv_ma.dropna()) > 0:
            if float(obv.iloc[-1]) > float(obv_ma.iloc[-1]) * 1.05:
                obv_trend = "资金流入"
            elif float(obv.iloc[-1]) < float(obv_ma.iloc[-1]) * 0.95:
                obv_trend = "资金流出"

        # 大单压力
        avg_amount = float((closes * volumes).tail(5).mean())
        avg_amount_20 = float((closes * volumes).tail(20).mean())
        pressure = avg_amount / avg_amount_20 if avg_amount_20 > 0 else 1.0

        return {
            "model": "Smart Money Flow",
            "cmf_20": round(cmf, 4),
            "obv_trend": obv_trend,
            "capital_pressure": round(pressure, 2),
            "signal": "主力吸筹" if cmf > 0.1 else ("主力出货" if cmf < -0.1 else "观望"),
        }

    # ================================================================
    #  量化综合评分
    # ================================================================

    def _calc_quant_score(self, result: Dict) -> float:
        score = 50.0  # 基准

        factors = result.get("factors", {})
        risk = result.get("risk_metrics", {})
        mom = result.get("momentum", {})
        smart = result.get("smart_money", {})

        # Alpha 贡献
        alpha = factors.get("alpha", 0)
        score += min(max(alpha * 100, -15), 15)

        # Sharpe 贡献
        sharpe = risk.get("sharpe_ratio", 0)
        if sharpe > 1.5:
            score += 15
        elif sharpe > 0.5:
            score += 8
        elif sharpe < -0.5:
            score -= 12

        # 最大回撤
        mdd = abs(risk.get("max_drawdown", 0))
        if mdd > 40:
            score -= 15
        elif mdd > 25:
            score -= 8
        elif mdd < 10:
            score += 5

        # RSI 极端值
        rsi = mom.get("rsi_14", 50)
        if rsi > 80:
            score -= 5
        elif rsi < 20:
            score -= 3

        # 动量
        mom_60 = mom.get("momentum_60d", 0)
        score += min(max(mom_60 * 0.15, -8), 8)

        # CMF
        cmf = smart.get("cmf_20", 0)
        score += min(max(cmf * 30, -8), 8)

        return round(max(0, min(100, score)), 1)

    @staticmethod
    def _score_to_level(score: float) -> str:
        if score >= 75:
            return "强烈推荐关注"
        elif score >= 60:
            return "量化信号偏多"
        elif score >= 45:
            return "信号中性"
        elif score >= 30:
            return "量化信号偏空"
        else:
            return "建议规避"
