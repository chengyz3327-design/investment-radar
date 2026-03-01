"""
命令行扫描工具 - 投资避雷
"""
import sys
import os
import argparse
from pathlib import Path

# 设置控制台编码
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.data_fetcher import DataFetcher
from src.risk_scorer import RiskScorer, RiskLevel


def get_level_symbol(level: RiskLevel) -> str:
    """根据风险等级返回符号"""
    symbol_map = {
        RiskLevel.SAFE: "[OK]",
        RiskLevel.GOOD: "[+]",
        RiskLevel.CAUTION: "[!]",
        RiskLevel.WARNING: "[!!]",
        RiskLevel.DANGER: "[X]",
    }
    return symbol_map.get(level, "[ ]")


def scan_stock(stock_code: str):
    """扫描单只股票"""
    print("\n" + "="*60)
    print("  投资避雷 - 股票风险扫描")
    print("  避开雷区，守护本金")
    print("="*60 + "\n")
    
    fetcher = DataFetcher()
    scorer = RiskScorer()
    
    print(f"正在扫描股票: {stock_code} ...\n")
    
    # 获取数据
    data = fetcher.get_all_data(stock_code)
    
    if not data.get("basic_info") and not data.get("price_info"):
        print(f"[X] 未找到股票 {stock_code}，请检查代码是否正确")
        return
    
    # 计算风险
    report = scorer.calculate_risk(data)
    
    # 显示结果
    print("-"*60)
    stock_name = report.stock_name or "未知"
    print(f"  {stock_name} ({report.stock_code})")
    print("-"*60)
    
    # 风险评分
    level_symbol = get_level_symbol(report.risk_level)
    
    print()
    print(f"  风险评分: {report.total_score:.0f} 分")
    print(f"  风险等级: {level_symbol} {report.risk_level.value}")
    print()
    
    # 风险摘要
    print(f"  >> {report.summary}")
    print()
    
    # 各项风险详情
    print("-"*60)
    print("  风险明细")
    print("-"*60)
    
    # 按风险等级排序
    sorted_items = sorted(report.risk_items, key=lambda x: x.score)
    
    for item in sorted_items:
        symbol = get_level_symbol(item.level)
        print()
        print(f"  {symbol} {item.name} [{item.category}]")
        print(f"      {item.detail}")
    
    # 统计
    print()
    print("-"*60)
    report_dict = report.to_dict()
    risk_count = report_dict["risk_count"]
    print(f"  风险统计: [X]危险 {risk_count['danger']} | [!!]警惕 {risk_count['warning']} | [!]注意 {risk_count['caution']}")
    print("-"*60)
    
    # 底部建议
    print()
    if report.risk_level == RiskLevel.DANGER:
        print("  *** 强烈建议：该股票风险极高，建议回避！***")
    elif report.risk_level == RiskLevel.WARNING:
        print("  ** 建议：该股票存在较大风险，请谨慎考虑 **")
    elif report.risk_level == RiskLevel.CAUTION:
        print("  * 建议：存在一定风险，建议深入研究后决策 *")
    else:
        print("  该股票基本面相对健康，但投资有风险，请自行判断")
    
    print()


def main():
    parser = argparse.ArgumentParser(
        description="投资避雷 - 股票风险扫描工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py 000001          扫描平安银行
  python main.py 600519          扫描贵州茅台
  python main.py 300750          扫描宁德时代
  python main.py --api           启动API服务
  
风险等级说明:
  [OK] 安全 (90-100分)  - 各项指标正常
  [+]  良好 (70-89分)   - 风险较低
  [!]  注意 (50-69分)   - 中等风险
  [!!] 警惕 (30-49分)   - 中高风险
  [X]  危险 (0-29分)    - 高风险
        """
    )
    parser.add_argument("stock_code", nargs="?", default=None, help="股票代码，如 000001、600519")
    parser.add_argument("--api", action="store_true", help="启动API服务")
    parser.add_argument("--port", type=int, default=8000, help="API端口号")
    
    args = parser.parse_args()
    
    if args.api:
        import uvicorn
        from src.api import app
        print("\n启动投资避雷 API 服务...")
        print(f"访问地址: http://localhost:{args.port}")
        print(f"API文档: http://localhost:{args.port}/docs\n")
        uvicorn.run(app, host="0.0.0.0", port=args.port)
    elif args.stock_code:
        scan_stock(args.stock_code)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
