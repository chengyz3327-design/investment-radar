"""
风险评分引擎 - 核心算法
"""
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import logging

from .config import RISK_WEIGHTS, RISK_THRESHOLDS

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """风险等级"""
    SAFE = "安全"
    GOOD = "良好"  
    CAUTION = "注意"
    WARNING = "警惕"
    DANGER = "危险"


@dataclass
class RiskItem:
    """单项风险"""
    name: str
    category: str  # 财务风险/股权风险/合规风险/市场风险
    score: float   # 0-100，100为无风险
    level: RiskLevel
    detail: str
    weight: float


@dataclass
class RiskReport:
    """风险报告"""
    stock_code: str
    stock_name: str
    total_score: float
    risk_level: RiskLevel
    risk_items: List[RiskItem]
    summary: str
    fetch_time: str
    quant_analysis: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "total_score": self.total_score,
            "risk_level": self.risk_level.value,
            "risk_items": [
                {
                    "name": item.name,
                    "category": item.category,
                    "score": item.score,
                    "level": item.level.value,
                    "detail": item.detail,
                    "weight": item.weight,
                }
                for item in self.risk_items
            ],
            "summary": self.summary,
            "fetch_time": self.fetch_time,
            "risk_count": {
                "danger": len([i for i in self.risk_items if i.level == RiskLevel.DANGER]),
                "warning": len([i for i in self.risk_items if i.level == RiskLevel.WARNING]),
                "caution": len([i for i in self.risk_items if i.level == RiskLevel.CAUTION]),
            }
        }
        if self.quant_analysis:
            result["quant_analysis"] = self.quant_analysis
        return result


class RiskScorer:
    """风险评分器"""
    
    def __init__(self):
        self.weights = RISK_WEIGHTS
        self.thresholds = RISK_THRESHOLDS
    
    def calculate_risk(self, data: Dict[str, Any]) -> RiskReport:
        """计算综合风险评分"""
        risk_items = []
        
        # 1. ST状态检测
        risk_items.append(self._check_st_status(data))
        
        # 2. 质押比例检测
        risk_items.append(self._check_pledge_ratio(data))
        
        # 3. 商誉风险检测
        risk_items.append(self._check_goodwill(data))
        
        # 4. 现金流检测
        risk_items.append(self._check_cashflow(data))
        
        # 5. 应收账款检测
        risk_items.append(self._check_receivables(data))
        
        # 6. 盈利能力检测
        risk_items.append(self._check_profitability(data))
        
        # 7. 审计意见检测
        risk_items.append(self._check_audit(data))
        
        # 8. 股东减持检测
        risk_items.append(self._check_shareholder_reduce(data))
        
        # 9. 股价跌幅检测
        risk_items.append(self._check_price_drop(data))
        
        # 10. 负债率检测
        risk_items.append(self._check_debt_ratio(data))
        
        # 过滤None
        risk_items = [item for item in risk_items if item is not None]
        
        # 计算加权总分
        total_score = self._calculate_total_score(risk_items)
        risk_level = self._get_risk_level(total_score)
        
        # 生成摘要
        summary = self._generate_summary(risk_items, risk_level)
        
        # 获取股票名称
        stock_name = ""
        if data.get("basic_info"):
            stock_name = data["basic_info"].get("name", "")
        elif data.get("price_info"):
            stock_name = data["price_info"].get("name", "")
        
        return RiskReport(
            stock_code=data.get("code", ""),
            stock_name=stock_name,
            total_score=round(total_score, 1),
            risk_level=risk_level,
            risk_items=risk_items,
            summary=summary,
            fetch_time=data.get("fetch_time", ""),
            quant_analysis=data.get("quant_analysis"),
        )
    
    def _check_st_status(self, data: Dict) -> RiskItem:
        """检测ST状态"""
        st_data = data.get("st_status", {})
        is_st = st_data.get("is_st", False)
        st_type = st_data.get("st_type")
        
        if st_type == "*ST":
            return RiskItem(
                name="ST状态",
                category="合规风险",
                score=0,
                level=RiskLevel.DANGER,
                detail=f"股票被标记为*ST，存在退市风险",
                weight=self.weights["st_status"]
            )
        elif st_type == "ST":
            return RiskItem(
                name="ST状态",
                category="合规风险",
                score=30,
                level=RiskLevel.WARNING,
                detail=f"股票被标记为ST，存在经营异常",
                weight=self.weights["st_status"]
            )
        else:
            return RiskItem(
                name="ST状态",
                category="合规风险",
                score=100,
                level=RiskLevel.SAFE,
                detail="正常状态",
                weight=self.weights["st_status"]
            )
    
    def _check_pledge_ratio(self, data: Dict) -> RiskItem:
        """检测质押比例"""
        pledge_data = data.get("pledge", {})
        ratio = pledge_data.get("pledge_ratio", 0)
        
        if ratio >= 80:
            return RiskItem(
                name="股权质押",
                category="股权风险",
                score=0,
                level=RiskLevel.DANGER,
                detail=f"大股东质押比例{ratio:.1f}%，超过80%警戒线，存在平仓风险",
                weight=self.weights["pledge_ratio"]
            )
        elif ratio >= 50:
            return RiskItem(
                name="股权质押",
                category="股权风险",
                score=40,
                level=RiskLevel.WARNING,
                detail=f"大股东质押比例{ratio:.1f}%，较高",
                weight=self.weights["pledge_ratio"]
            )
        elif ratio >= 30:
            return RiskItem(
                name="股权质押",
                category="股权风险",
                score=70,
                level=RiskLevel.CAUTION,
                detail=f"大股东质押比例{ratio:.1f}%，需关注",
                weight=self.weights["pledge_ratio"]
            )
        else:
            return RiskItem(
                name="股权质押",
                category="股权风险",
                score=100,
                level=RiskLevel.SAFE,
                detail=f"大股东质押比例{ratio:.1f}%，处于安全范围",
                weight=self.weights["pledge_ratio"]
            )
    
    def _check_goodwill(self, data: Dict) -> RiskItem:
        """检测商誉风险"""
        goodwill_data = data.get("goodwill")
        if not goodwill_data:
            return RiskItem(
                name="商誉风险",
                category="财务风险",
                score=100,
                level=RiskLevel.SAFE,
                detail="无商誉或数据未获取",
                weight=self.weights["high_goodwill"]
            )
        
        ratio = goodwill_data.get("goodwill_ratio", 0)
        goodwill = goodwill_data.get("goodwill", 0) / 100000000  # 转为亿
        
        if ratio >= 50:
            return RiskItem(
                name="商誉风险",
                category="财务风险",
                score=10,
                level=RiskLevel.DANGER,
                detail=f"商誉{goodwill:.1f}亿，占净资产{ratio:.1f}%，存在重大减值风险",
                weight=self.weights["high_goodwill"]
            )
        elif ratio >= self.thresholds["goodwill_ratio"] * 100:
            return RiskItem(
                name="商誉风险",
                category="财务风险",
                score=50,
                level=RiskLevel.WARNING,
                detail=f"商誉{goodwill:.1f}亿，占净资产{ratio:.1f}%，需关注减值风险",
                weight=self.weights["high_goodwill"]
            )
        else:
            return RiskItem(
                name="商誉风险",
                category="财务风险",
                score=100,
                level=RiskLevel.SAFE,
                detail=f"商誉占比{ratio:.1f}%，处于安全范围",
                weight=self.weights["high_goodwill"]
            )
    
    def _check_cashflow(self, data: Dict) -> RiskItem:
        """检测现金流"""
        cf_data = data.get("cashflow")
        if not cf_data:
            return RiskItem(
                name="经营现金流",
                category="财务风险",
                score=80,
                level=RiskLevel.GOOD,
                detail="现金流数据未获取",
                weight=self.weights["negative_cashflow"]
            )
        
        is_negative = cf_data.get("is_negative", False)
        continuous = cf_data.get("continuous_negative", False)
        cf_per_share = cf_data.get("cf_per_share", cf_data.get("operating_cashflow", 0))
        
        if continuous:
            return RiskItem(
                name="经营现金流",
                category="财务风险",
                score=20,
                level=RiskLevel.DANGER,
                detail=f"每股经营现金流{cf_per_share:.2f}元，连续多期为负，造血能力严重不足",
                weight=self.weights["negative_cashflow"]
            )
        elif is_negative:
            return RiskItem(
                name="经营现金流",
                category="财务风险",
                score=50,
                level=RiskLevel.WARNING,
                detail=f"每股经营现金流{cf_per_share:.2f}元，为负值需关注",
                weight=self.weights["negative_cashflow"]
            )
        else:
            return RiskItem(
                name="经营现金流",
                category="财务风险",
                score=100,
                level=RiskLevel.SAFE,
                detail=f"每股经营现金流{cf_per_share:.2f}元，正常",
                weight=self.weights["negative_cashflow"]
            )
    
    def _check_receivables(self, data: Dict) -> RiskItem:
        """检测应收账款"""
        recv_data = data.get("receivables")
        if not recv_data:
            return RiskItem(
                name="应收账款",
                category="财务风险",
                score=80,
                level=RiskLevel.GOOD,
                detail="应收账款数据未获取",
                weight=self.weights["receivables_growth"]
            )
        
        growth = recv_data.get("receivables_growth", 0)
        is_abnormal = recv_data.get("is_abnormal", False)
        
        if growth > 100:
            return RiskItem(
                name="应收账款",
                category="财务风险",
                score=20,
                level=RiskLevel.DANGER,
                detail=f"应收账款同比增长{growth:.1f}%，增长异常，可能存在收入质量问题",
                weight=self.weights["receivables_growth"]
            )
        elif is_abnormal:
            return RiskItem(
                name="应收账款",
                category="财务风险",
                score=50,
                level=RiskLevel.WARNING,
                detail=f"应收账款同比增长{growth:.1f}%，增速较快需关注",
                weight=self.weights["receivables_growth"]
            )
        else:
            return RiskItem(
                name="应收账款",
                category="财务风险",
                score=100,
                level=RiskLevel.SAFE,
                detail=f"应收账款增长{growth:.1f}%，正常范围",
                weight=self.weights["receivables_growth"]
            )
    
    def _check_profitability(self, data: Dict) -> RiskItem:
        """检测盈利能力"""
        fin_data = data.get("financial")
        if not fin_data:
            return RiskItem(
                name="盈利能力",
                category="财务风险",
                score=80,
                level=RiskLevel.GOOD,
                detail="财务数据未获取",
                weight=self.weights["continuous_loss"]
            )
        
        net_profit = fin_data.get("net_profit", 0)
        net_profit_yoy = fin_data.get("net_profit_yoy", 0)
        continuous_loss = fin_data.get("continuous_loss", False)
        roe = fin_data.get("roe", 0)
        
        profit_yi = net_profit / 1e8 if abs(net_profit) >= 1e8 else net_profit / 1e4
        unit = "亿" if abs(net_profit) >= 1e8 else "万"
        
        if continuous_loss:
            return RiskItem(
                name="盈利能力",
                category="财务风险",
                score=5,
                level=RiskLevel.DANGER,
                detail=f"净利润{profit_yi:.2f}{unit}，连续亏损，存在退市风险",
                weight=self.weights["continuous_loss"]
            )
        elif net_profit < 0:
            return RiskItem(
                name="盈利能力",
                category="财务风险",
                score=20,
                level=RiskLevel.DANGER,
                detail=f"净利润{profit_yi:.2f}{unit}，公司处于亏损状态",
                weight=self.weights["continuous_loss"]
            )
        elif net_profit_yoy < -50:
            return RiskItem(
                name="盈利能力",
                category="财务风险",
                score=40,
                level=RiskLevel.WARNING,
                detail=f"净利润同比下降{abs(net_profit_yoy):.1f}%，业绩大幅下滑",
                weight=self.weights["continuous_loss"]
            )
        elif net_profit_yoy < -20:
            return RiskItem(
                name="盈利能力",
                category="财务风险",
                score=70,
                level=RiskLevel.CAUTION,
                detail=f"净利润同比下降{abs(net_profit_yoy):.1f}%，需关注",
                weight=self.weights["continuous_loss"]
            )
        else:
            return RiskItem(
                name="盈利能力",
                category="财务风险",
                score=100,
                level=RiskLevel.SAFE,
                detail=f"净利润{profit_yi:.2f}{unit}，同比{'+' if net_profit_yoy>=0 else ''}{net_profit_yoy:.1f}%",
                weight=self.weights["continuous_loss"]
            )
    
    def _check_audit(self, data: Dict) -> RiskItem:
        """检测审计意见"""
        audit_data = data.get("audit", {})
        is_abnormal = audit_data.get("is_abnormal", False)
        opinion = audit_data.get("opinion_type", "标准无保留意见")
        
        if is_abnormal:
            return RiskItem(
                name="审计意见",
                category="合规风险",
                score=10,
                level=RiskLevel.DANGER,
                detail=f"审计意见：{opinion}，财务数据可靠性存疑",
                weight=self.weights["audit_opinion"]
            )
        else:
            return RiskItem(
                name="审计意见",
                category="合规风险",
                score=100,
                level=RiskLevel.SAFE,
                detail="审计意见正常",
                weight=self.weights["audit_opinion"]
            )
    
    def _check_shareholder_reduce(self, data: Dict) -> RiskItem:
        """检测股东减持"""
        sh_data = data.get("shareholder", {})
        recent_reduce = sh_data.get("recent_reduce", False)
        reduce_count = sh_data.get("reduce_count", 0)
        
        if reduce_count >= 3:
            return RiskItem(
                name="股东减持",
                category="股权风险",
                score=30,
                level=RiskLevel.WARNING,
                detail=f"近期有{reduce_count}笔高管/大股东减持，需警惕",
                weight=self.weights["shareholder_reduce"]
            )
        elif recent_reduce:
            return RiskItem(
                name="股东减持",
                category="股权风险",
                score=60,
                level=RiskLevel.CAUTION,
                detail="近期存在股东减持行为",
                weight=self.weights["shareholder_reduce"]
            )
        else:
            return RiskItem(
                name="股东减持",
                category="股权风险",
                score=100,
                level=RiskLevel.SAFE,
                detail="近期无重大减持",
                weight=self.weights["shareholder_reduce"]
            )
    
    def _check_price_drop(self, data: Dict) -> RiskItem:
        """检测股价跌幅"""
        price_data = data.get("price_history")
        if not price_data:
            return RiskItem(
                name="股价走势",
                category="市场风险",
                score=80,
                level=RiskLevel.GOOD,
                detail="价格数据未获取",
                weight=self.weights["price_drop"]
            )
        
        drop = price_data.get("drop_from_high", 0)
        current = price_data.get("current_price", 0)
        high = price_data.get("high_52week", 0)
        
        if drop >= 50:
            return RiskItem(
                name="股价走势",
                category="市场风险",
                score=10,
                level=RiskLevel.DANGER,
                detail=f"股价{current}元，较52周高点{high}元下跌{drop:.1f}%，跌幅巨大",
                weight=self.weights["price_drop"]
            )
        elif drop >= 30:
            return RiskItem(
                name="股价走势",
                category="市场风险",
                score=40,
                level=RiskLevel.WARNING,
                detail=f"股价{current}元，较52周高点{high}元下跌{drop:.1f}%",
                weight=self.weights["price_drop"]
            )
        elif drop >= 15:
            return RiskItem(
                name="股价走势",
                category="市场风险",
                score=75,
                level=RiskLevel.CAUTION,
                detail=f"股价{current}元，较52周高点{high}元回撤{drop:.1f}%",
                weight=self.weights["price_drop"]
            )
        else:
            return RiskItem(
                name="股价走势",
                category="市场风险",
                score=100,
                level=RiskLevel.SAFE,
                detail=f"股价{current}元，较52周高点回撤{drop:.1f}%，走势正常",
                weight=self.weights["price_drop"]
            )
    
    def _check_debt_ratio(self, data: Dict) -> Optional[RiskItem]:
        """检测资产负债率"""
        fin_data = data.get("financial")
        if not fin_data:
            return None
        
        debt_ratio = fin_data.get("debt_ratio", 0)
        if debt_ratio <= 0:
            return None
        
        # 银行等金融行业负债率天然高，用名称做简单判断
        is_financial = False
        name = ""
        if data.get("basic_info"):
            name = data["basic_info"].get("name", "")
        elif data.get("price_info"):
            name = data["price_info"].get("name", "")
        fin_keywords = ["银行", "保险", "证券", "信托", "金融"]
        is_financial = any(k in name for k in fin_keywords)
        
        if is_financial:
            # 金融行业负债率阈值更高
            if debt_ratio >= 97:
                score, level = 30, RiskLevel.WARNING
            elif debt_ratio >= 95:
                score, level = 70, RiskLevel.CAUTION
            else:
                score, level = 100, RiskLevel.SAFE
        else:
            if debt_ratio >= 80:
                score, level = 20, RiskLevel.DANGER
            elif debt_ratio >= 65:
                score, level = 50, RiskLevel.WARNING
            elif debt_ratio >= 50:
                score, level = 75, RiskLevel.CAUTION
            else:
                score, level = 100, RiskLevel.SAFE
        
        return RiskItem(
            name="资产负债率",
            category="财务风险",
            score=score,
            level=level,
            detail=f"资产负债率{debt_ratio:.1f}%{'（金融行业）' if is_financial else ''}",
            weight=0.05,
        )
    
    def _calculate_total_score(self, risk_items: List[RiskItem]) -> float:
        """计算加权总分"""
        if not risk_items:
            return 100.0
        
        total_weight = sum(item.weight for item in risk_items)
        if total_weight == 0:
            return 100.0
        
        weighted_score = sum(item.score * item.weight for item in risk_items)
        return weighted_score / total_weight
    
    def _get_risk_level(self, score: float) -> RiskLevel:
        """根据分数判断风险等级"""
        if score >= 90:
            return RiskLevel.SAFE
        elif score >= 70:
            return RiskLevel.GOOD
        elif score >= 50:
            return RiskLevel.CAUTION
        elif score >= 30:
            return RiskLevel.WARNING
        else:
            return RiskLevel.DANGER
    
    def _generate_summary(self, risk_items: List[RiskItem], risk_level: RiskLevel) -> str:
        """生成风险摘要"""
        danger_items = [i for i in risk_items if i.level == RiskLevel.DANGER]
        warning_items = [i for i in risk_items if i.level == RiskLevel.WARNING]
        
        if risk_level == RiskLevel.DANGER:
            issues = [i.name for i in danger_items[:3]]
            return f"高风险警告！检出{len(danger_items)}项重大风险：{', '.join(issues)}，建议回避"
        elif risk_level == RiskLevel.WARNING:
            issues = [i.name for i in (danger_items + warning_items)[:3]]
            return f"中高风险！存在{len(danger_items)}项重大风险和{len(warning_items)}项警示：{', '.join(issues)}"
        elif risk_level == RiskLevel.CAUTION:
            return f"中等风险，存在{len(warning_items)}项需关注的指标，建议深入研究后决策"
        elif risk_level == RiskLevel.GOOD:
            return "风险较低，基本面相对健康，但仍需关注市场变化"
        else:
            return "风险较低，各项指标正常，基本面健康"
