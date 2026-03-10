"""
数据采集模块 - 使用AKShare获取股票数据
"""
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import logging
import time

from src.quant_factors import QuantFactorEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataFetcher:
    """股票数据采集器"""

    def __init__(self):
        self._stock_list_cache = None
        self._stock_list_time = 0
        self._pledge_cache = None
        self._pledge_time = 0
        self._ths_fin_cache = {}
        self._info_cache = {}
        self._daily_cache = {}
        self._cache_ttl = 300  # 5分钟
        self._quant_engine = QuantFactorEngine()
        self._executor = ThreadPoolExecutor(max_workers=3)
        # 超时与重试配置
        self._timeout_daily = 15
        self._timeout_financial = 15
        self._timeout_pledge = 20
        self._max_retries = 2
        self._retry_base_delay = 1.0

    # ============================================================
    #  工具方法
    # ============================================================

    @staticmethod
    def _parse_value(value) -> float:
        """解析带单位的财务数值，如 '383.39亿' / '-9212.28万' / '-3.50%' / False"""
        if value is None or value is False:
            return 0.0
        try:
            if pd.isna(value):
                return 0.0
        except (TypeError, ValueError):
            pass
        s = str(value).strip()
        if not s or s.lower() in ('false', 'none', 'nan', '--', '-'):
            return 0.0
        s = s.replace('%', '')
        multiplier = 1.0
        if '亿' in s:
            s = s.replace('亿', '')
            multiplier = 1e8
        elif '万' in s:
            s = s.replace('万', '')
            multiplier = 1e4
        try:
            return float(s) * multiplier
        except ValueError:
            return 0.0

    @staticmethod
    def _parse_pct(value) -> float:
        """解析百分比值，如 '-3.50%' -> -3.50"""
        if value is None or value is False:
            return 0.0
        try:
            if pd.isna(value):
                return 0.0
        except (TypeError, ValueError):
            pass
        s = str(value).strip()
        if not s or s.lower() in ('false', 'none', 'nan', '--', '-'):
            return 0.0
        s = s.replace('%', '')
        try:
            return float(s)
        except ValueError:
            return 0.0

    @staticmethod
    def _get_market_prefix(stock_code: str) -> str:
        if stock_code.startswith(('6', '9')):
            return 'sh'
        return 'sz'

    def _safe_call(self, func: Callable, timeout: float, desc: str):
        """带超时和重试的安全调用包装器，返回 (result, warning_or_None)"""
        for attempt in range(self._max_retries + 1):
            try:
                future = self._executor.submit(func)
                result = future.result(timeout=timeout)
                return result, None
            except FutureTimeout:
                logger.warning(f"{desc} 超时(第{attempt+1}次, {timeout}s)")
            except Exception as e:
                logger.warning(f"{desc} 异常(第{attempt+1}次): {type(e).__name__}: {e}")
            if attempt < self._max_retries:
                delay = self._retry_base_delay * (2 ** attempt)
                time.sleep(delay)
        return None, f"{desc}获取失败(超时或服务不可用)"

    # ============================================================
    #  缓存层
    # ============================================================

    def _get_stock_list(self) -> pd.DataFrame:
        now = time.time()
        if self._stock_list_cache is None or (now - self._stock_list_time) > 86400:
            # 优先使用内置静态股票列表（避免海外服务器访问慢）
            try:
                import os
                csv_path = os.path.join(os.path.dirname(__file__), "data", "stock_list.csv")
                if os.path.exists(csv_path):
                    self._stock_list_cache = pd.read_csv(csv_path, dtype={"code": str})
                    self._stock_list_cache['code'] = self._stock_list_cache['code'].str.zfill(6)
                    self._stock_list_time = now
                    logger.info(f"从静态文件加载 {len(self._stock_list_cache)} 只股票")
                    return self._stock_list_cache
            except Exception as e:
                logger.warning(f"加载静态股票列表失败: {e}")
            # 回退到在线获取
            try:
                self._stock_list_cache = ak.stock_info_a_code_name()
                self._stock_list_cache['code'] = (
                    self._stock_list_cache['code'].astype(str).str.zfill(6)
                )
                self._stock_list_time = now
            except Exception as e:
                logger.error(f"在线获取股票列表失败: {e}")
                if self._stock_list_cache is None:
                    self._stock_list_cache = pd.DataFrame(columns=['code', 'name'])
        return self._stock_list_cache

    def _get_ths_financial(self, stock_code: str, warnings: List[str] = None) -> Optional[pd.DataFrame]:
        if stock_code not in self._ths_fin_cache:
            def _fetch():
                return ak.stock_financial_abstract_ths(
                    symbol=stock_code, indicator="按报告期"
                )
            result, warn = self._safe_call(_fetch, self._timeout_financial, f"THS财务数据({stock_code})")
            if warn and warnings is not None:
                warnings.append(warn)
            if result is not None and not result.empty:
                self._ths_fin_cache[stock_code] = result
            else:
                self._ths_fin_cache[stock_code] = None
        return self._ths_fin_cache[stock_code]

    def _get_daily_data(self, stock_code: str, warnings: List[str] = None) -> Optional[pd.DataFrame]:
        """获取并缓存52周日线数据（一次请求，多处复用）"""
        if stock_code in self._daily_cache:
            return self._daily_cache[stock_code]
        symbol = f"{self._get_market_prefix(stock_code)}{stock_code}"
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')

        def _fetch():
            return ak.stock_zh_a_daily(
                symbol=symbol, start_date=start_date,
                end_date=end_date, adjust="qfq",
            )
        result, warn = self._safe_call(_fetch, self._timeout_daily, f"日线数据({stock_code})")
        if warn and warnings is not None:
            warnings.append(warn)
        if result is not None and not result.empty:
            self._daily_cache[stock_code] = result
        else:
            self._daily_cache[stock_code] = None
        return self._daily_cache[stock_code]

    def _get_pledge_table(self, warnings: List[str] = None) -> Optional[pd.DataFrame]:
        now = time.time()
        if self._pledge_cache is None or (now - self._pledge_time) > 7200:
            def _fetch():
                return ak.stock_gpzy_pledge_ratio_em()
            result, warn = self._safe_call(_fetch, self._timeout_pledge, "质押数据表")
            if warn and warnings is not None:
                warnings.append(warn)
            if result is not None:
                result['股票代码'] = result['股票代码'].astype(str).str.zfill(6)
                self._pledge_cache = result
                self._pledge_time = now
            else:
                return None
        return self._pledge_cache

    # ============================================================
    #  基本信息
    # ============================================================

    def get_stock_info(self, stock_code: str) -> Optional[Dict[str, Any]]:
        if stock_code in self._info_cache:
            return self._info_cache[stock_code]
        try:
            stock_list = self._get_stock_list()
            match = stock_list[stock_list['code'] == stock_code]
            if match.empty:
                match = stock_list[
                    stock_list['name'].str.contains(stock_code, na=False)
                ]
            if match.empty:
                self._info_cache[stock_code] = None
                return None
            row = match.iloc[0]
            result = {"code": row['code'], "name": row['name']}
            self._info_cache[stock_code] = result
            return result
        except Exception as e:
            logger.error(f"获取股票信息失败: {e}")
            return None

    # ============================================================
    #  行情数据（复用日线缓存）
    # ============================================================

    def get_stock_price(self, stock_code: str) -> Optional[Dict[str, Any]]:
        df = self._get_daily_data(stock_code)
        if df is None or df.empty:
            return None
        latest = df.iloc[-1]
        info = self.get_stock_info(stock_code)
        name = info['name'] if info else ""
        return {
            "code": stock_code,
            "name": name,
            "price": float(latest['close']),
            "high": float(latest['high']),
            "low": float(latest['low']),
            "volume": float(latest['volume']),
        }

    # ============================================================
    #  财务数据
    # ============================================================

    def get_financial_data(self, stock_code: str) -> Optional[Dict[str, Any]]:
        df = self._get_ths_financial(stock_code)
        if df is None:
            return None
        try:
            r = df.iloc[0]
            net_profit = self._parse_value(r.get("净利润", 0))
            net_profit_yoy = self._parse_pct(r.get("净利润同比增长率", 0))
            revenue = self._parse_value(r.get("营业总收入", 0))
            revenue_yoy = self._parse_pct(r.get("营业总收入同比增长率", 0))
            roe = self._parse_pct(r.get("净资产收益率", 0))
            debt_ratio = self._parse_pct(r.get("资产负债率", 0))

            continuous_loss = False
            if net_profit < 0 and len(df) >= 2:
                prev_profit = self._parse_value(df.iloc[1].get("净利润", 0))
                if prev_profit < 0:
                    continuous_loss = True

            return {
                "report_date": str(r.get("报告期", "")),
                "net_profit": net_profit,
                "net_profit_yoy": net_profit_yoy,
                "revenue": revenue,
                "revenue_yoy": revenue_yoy,
                "roe": roe,
                "debt_ratio": debt_ratio,
                "continuous_loss": continuous_loss,
            }
        except Exception as e:
            logger.error(f"解析财务数据失败 {stock_code}: {e}")
            return None

    # ============================================================
    #  现金流
    # ============================================================

    def get_cashflow_data(self, stock_code: str) -> Optional[Dict[str, Any]]:
        df = self._get_ths_financial(stock_code)
        if df is None:
            return {"operating_cashflow": 0, "is_negative": False,
                    "continuous_negative": False, "negative_periods": 0}
        try:
            cf_per_share = self._parse_pct(df.iloc[0].get("每股经营现金流", 0))
            is_negative = cf_per_share < 0

            negative_periods = 0
            for i in range(min(len(df), 4)):
                val = self._parse_pct(df.iloc[i].get("每股经营现金流", 0))
                if val < 0:
                    negative_periods += 1
                else:
                    break
            continuous_negative = negative_periods >= 2

            return {
                "operating_cashflow": cf_per_share,
                "cf_per_share": cf_per_share,
                "is_negative": is_negative,
                "continuous_negative": continuous_negative,
                "negative_periods": negative_periods,
            }
        except Exception as e:
            logger.warning(f"解析现金流失败 {stock_code}: {e}")
            return {"operating_cashflow": 0, "is_negative": False,
                    "continuous_negative": False, "negative_periods": 0}

    # ============================================================
    #  质押数据
    # ============================================================

    def get_pledge_data(self, stock_code: str, warnings: List[str] = None) -> Optional[Dict[str, Any]]:
        table = self._get_pledge_table(warnings)
        if table is None:
            return {"pledge_ratio": 0, "pledge_count": 0}
        match = table[table['股票代码'] == stock_code]
        if match.empty:
            return {"pledge_ratio": 0, "pledge_count": 0}
        row = match.iloc[0]
        ratio = float(row.get('质押比例', 0)) if pd.notna(row.get('质押比例')) else 0
        count = int(row.get('质押笔数', 0)) if pd.notna(row.get('质押笔数')) else 0
        return {"pledge_ratio": ratio, "pledge_count": count}

    # ============================================================
    #  ST状态（复用 stock_info 缓存）
    # ============================================================

    def get_st_status(self, stock_code: str) -> Dict[str, Any]:
        info = self.get_stock_info(stock_code)
        if not info:
            return {"is_st": False, "st_type": None}
        name = info.get("name", "")
        st_type = None
        if "*ST" in name:
            st_type = "*ST"
        elif "ST" in name:
            st_type = "ST"
        return {"is_st": st_type is not None, "st_type": st_type}

    # ============================================================
    #  价格历史（复用日线缓存）
    # ============================================================

    def get_price_history(self, stock_code: str, days: int = 250) -> Optional[Dict[str, Any]]:
        df = self._get_daily_data(stock_code)
        if df is None or df.empty:
            return {"high_52week": 0, "low_52week": 0,
                    "current_price": 0, "drop_from_high": 0}
        high = float(df['high'].max())
        low = float(df['low'].min())
        current = float(df['close'].iloc[-1])
        drop = (high - current) / high * 100 if high > 0 else 0
        return {
            "high_52week": round(high, 2),
            "low_52week": round(low, 2),
            "current_price": round(current, 2),
            "drop_from_high": round(drop, 2),
        }

    # ============================================================
    #  简化/桩方法
    # ============================================================

    def get_shareholder_change(self, stock_code: str) -> Dict[str, Any]:
        return {"recent_reduce": False, "reduce_count": 0}

    def get_audit_opinion(self, stock_code: str) -> Dict[str, Any]:
        return {"opinion_type": "标准无保留意见", "is_abnormal": False}

    def get_goodwill_data(self, stock_code: str) -> Dict[str, Any]:
        return {"goodwill": 0, "total_equity": 0, "goodwill_ratio": 0}

    # ============================================================
    #  应收账款
    # ============================================================

    def get_receivables_data(self, stock_code: str) -> Dict[str, Any]:
        df = self._get_ths_financial(stock_code)
        if df is None or len(df) < 2:
            return {"receivables": 0, "receivables_growth": 0, "is_abnormal": False}
        try:
            curr_days = self._parse_pct(df.iloc[0].get("应收账款周转天数", 0))
            prev_days = self._parse_pct(df.iloc[1].get("应收账款周转天数", 0))
            growth = 0
            if prev_days > 0 and curr_days > 0:
                growth = (curr_days - prev_days) / prev_days * 100
            is_abnormal = growth > 50
            return {
                "receivables": curr_days,
                "receivables_growth": round(growth, 2),
                "is_abnormal": is_abnormal,
            }
        except Exception:
            return {"receivables": 0, "receivables_growth": 0, "is_abnormal": False}

    # ============================================================
    #  量化因子分析
    # ============================================================

    def get_quant_analysis(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """使用日线数据 + 财务数据计算量化因子"""
        try:
            daily_df = self._get_daily_data(stock_code)
            financial = self.get_financial_data(stock_code)
            price_info = self.get_price_history(stock_code)
            return self._quant_engine.analyze(daily_df, financial, price_info)
        except Exception as e:
            logger.error(f"量化因子分析失败 {stock_code}: {e}")
            return None

    # ============================================================
    #  汇总
    # ============================================================

    def get_all_data(self, stock_code: str) -> Dict[str, Any]:
        stock_code = stock_code.zfill(6)
        logger.info(f"开始采集股票 {stock_code} 的数据...")
        warnings: List[str] = []

        # 预加载缓存（减少重复调用）
        self.get_stock_info(stock_code)
        self._get_ths_financial(stock_code, warnings)
        self._get_daily_data(stock_code, warnings)

        result = {
            "code": stock_code,
            "fetch_time": datetime.now().isoformat(),
            "basic_info": self.get_stock_info(stock_code),
            "price_info": self.get_stock_price(stock_code),
            "financial": self.get_financial_data(stock_code),
            "pledge": self.get_pledge_data(stock_code, warnings),
            "shareholder": self.get_shareholder_change(stock_code),
            "st_status": self.get_st_status(stock_code),
            "audit": self.get_audit_opinion(stock_code),
            "goodwill": self.get_goodwill_data(stock_code),
            "cashflow": self.get_cashflow_data(stock_code),
            "receivables": self.get_receivables_data(stock_code),
            "price_history": self.get_price_history(stock_code),
            "quant_analysis": self.get_quant_analysis(stock_code),
            "warnings": warnings,
        }

        logger.info(f"股票 {stock_code} 数据采集完成 (warnings: {len(warnings)})")
        return result
