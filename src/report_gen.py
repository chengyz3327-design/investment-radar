"""
扫描报告图片生成模块
生成可分享的风险评估报告卡片
"""
import io
import base64
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

# 字体路径 (使用系统字体)
FONT_DIR = Path(__file__).parent.parent / "static" / "fonts"


def get_font(size: int, bold: bool = False):
    """获取字体，优先使用自定义字体，否则使用默认"""
    try:
        # 尝试使用 Windows 系统字体
        if bold:
            return ImageFont.truetype("msyhbd.ttc", size)  # 微软雅黑粗体
        return ImageFont.truetype("msyh.ttc", size)  # 微软雅黑
    except:
        try:
            # 备选字体
            return ImageFont.truetype("arial.ttf", size)
        except:
            return ImageFont.load_default()


def get_risk_color(level: str) -> tuple:
    """根据风险等级返回颜色"""
    colors = {
        "安全": (34, 197, 94),    # 绿色
        "良好": (59, 130, 246),   # 蓝色
        "注意": (234, 179, 8),    # 黄色
        "警惕": (249, 115, 22),   # 橙色
        "危险": (239, 68, 68),    # 红色
    }
    return colors.get(level, (100, 100, 100))


def get_score_color(score: int) -> tuple:
    """根据分数返回颜色"""
    if score >= 90:
        return (34, 197, 94)   # 绿色
    if score >= 70:
        return (59, 130, 246)  # 蓝色
    if score >= 50:
        return (234, 179, 8)   # 黄色
    if score >= 30:
        return (249, 115, 22)  # 橙色
    return (239, 68, 68)       # 红色


def generate_report_image(data: dict) -> bytes:
    """
    生成扫描报告图片
    
    Args:
        data: 扫描结果数据
    
    Returns:
        PNG 图片字节数据
    """
    # 图片尺寸
    width, height = 600, 800
    
    # 创建画布
    img = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # 提取数据
    stock_code = data.get("stock_code", "------")
    stock_name = data.get("stock_name", "未知")
    total_score = int(data.get("total_score", 0))
    risk_level = data.get("risk_level", "未知")
    
    # 颜色
    score_color = get_score_color(total_score)
    risk_color = get_risk_color(risk_level)
    
    # 字体
    font_title = get_font(28, bold=True)
    font_large = get_font(72, bold=True)
    font_medium = get_font(24)
    font_small = get_font(18)
    font_tiny = get_font(14)
    
    y = 30
    
    # 顶部标题
    draw.text((width // 2, y), "投资避雷", fill=(30, 41, 59), font=font_title, anchor="mt")
    y += 35
    draw.text((width // 2, y), "股票风险评估报告", fill=(100, 116, 139), font=font_small, anchor="mt")
    y += 50
    
    # 分割线
    draw.line([(50, y), (width - 50, y)], fill=(226, 232, 240), width=2)
    y += 30
    
    # 股票信息
    draw.text((width // 2, y), stock_name, fill=(30, 41, 59), font=font_title, anchor="mt")
    y += 40
    draw.text((width // 2, y), stock_code, fill=(100, 116, 139), font=font_medium, anchor="mt")
    y += 60
    
    # 大分数圆圈
    circle_center = (width // 2, y + 80)
    circle_radius = 80
    
    # 绘制圆圈背景
    draw.ellipse(
        [circle_center[0] - circle_radius, circle_center[1] - circle_radius,
         circle_center[0] + circle_radius, circle_center[1] + circle_radius],
        fill=score_color + (30,),  # 淡色背景
        outline=score_color,
        width=4
    )
    
    # 分数
    draw.text(circle_center, str(total_score), fill=score_color, font=font_large, anchor="mm")
    y += 180
    
    # 风险等级标签
    level_width = 100
    level_height = 36
    level_x = width // 2 - level_width // 2
    draw.rounded_rectangle(
        [level_x, y, level_x + level_width, y + level_height],
        radius=18,
        fill=risk_color
    )
    draw.text((width // 2, y + level_height // 2), risk_level, fill=(255, 255, 255), font=font_medium, anchor="mm")
    y += 60
    
    # 分割线
    draw.line([(50, y), (width - 50, y)], fill=(226, 232, 240), width=1)
    y += 25
    
    # 风险摘要
    risk_summary = data.get("risk_summary", {})
    if risk_summary:
        # 绘制风险项
        summary_items = [
            ("财务风险", risk_summary.get("financial", {}).get("score", 100)),
            ("股权风险", risk_summary.get("equity", {}).get("score", 100)),
            ("合规风险", risk_summary.get("compliance", {}).get("score", 100)),
            ("市场风险", risk_summary.get("market", {}).get("score", 100)),
        ]
        
        bar_width = 400
        bar_height = 12
        bar_x = (width - bar_width) // 2
        
        for label, score in summary_items:
            # 标签
            draw.text((bar_x, y), label, fill=(71, 85, 105), font=font_small, anchor="lt")
            draw.text((bar_x + bar_width, y), f"{score}分", fill=(100, 116, 139), font=font_small, anchor="rt")
            y += 28
            
            # 进度条背景
            draw.rounded_rectangle(
                [bar_x, y, bar_x + bar_width, y + bar_height],
                radius=6,
                fill=(241, 245, 249)
            )
            
            # 进度条
            fill_width = int(bar_width * score / 100)
            if fill_width > 0:
                bar_color = get_score_color(score)
                draw.rounded_rectangle(
                    [bar_x, y, bar_x + fill_width, y + bar_height],
                    radius=6,
                    fill=bar_color
                )
            y += 30
    
    y += 20
    
    # 底部信息
    draw.line([(50, y), (width - 50, y)], fill=(226, 232, 240), width=1)
    y += 20
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    draw.text((width // 2, y), f"生成时间: {now}", fill=(148, 163, 184), font=font_tiny, anchor="mt")
    y += 25
    draw.text((width // 2, y), "投资避雷 · 机构级量化风控", fill=(148, 163, 184), font=font_tiny, anchor="mt")
    y += 25
    draw.text((width // 2, y), "基于 Fama-French 五因子模型", fill=(203, 213, 225), font=font_tiny, anchor="mt")
    
    # 保存为字节
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", quality=95)
    buffer.seek(0)
    
    return buffer.getvalue()


def generate_report_base64(data: dict) -> str:
    """生成报告图片的 Base64 编码"""
    img_bytes = generate_report_image(data)
    return base64.b64encode(img_bytes).decode("utf-8")
