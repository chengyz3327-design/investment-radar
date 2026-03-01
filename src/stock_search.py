"""
股票搜索模块 - 支持拼音、模糊搜索
"""
import re
from pypinyin import lazy_pinyin, Style
import pandas as pd
from functools import lru_cache

# 热门股票（用于空搜索时展示）
HOT_STOCKS = [
    {"code": "600519", "name": "贵州茅台"},
    {"code": "000001", "name": "平安银行"},
    {"code": "000858", "name": "五粮液"},
    {"code": "601318", "name": "中国平安"},
    {"code": "600036", "name": "招商银行"},
    {"code": "000333", "name": "美的集团"},
    {"code": "600900", "name": "长江电力"},
    {"code": "601012", "name": "隆基绿能"},
]


def get_pinyin_full(text: str) -> str:
    """获取完整拼音 (小写无空格)"""
    return "".join(lazy_pinyin(text)).lower()


def get_pinyin_initials(text: str) -> str:
    """获取拼音首字母"""
    return "".join(lazy_pinyin(text, style=Style.FIRST_LETTER)).lower()


@lru_cache(maxsize=1)
def build_search_index(stock_list_tuple):
    """构建搜索索引（带拼音）"""
    # 将元组转回 DataFrame
    stock_list = pd.DataFrame(list(stock_list_tuple), columns=["code", "name"])
    
    # 添加拼音字段
    stock_list["pinyin_full"] = stock_list["name"].apply(get_pinyin_full)
    stock_list["pinyin_initials"] = stock_list["name"].apply(get_pinyin_initials)
    
    return stock_list


def search_stocks(query: str, stock_list_df: pd.DataFrame, limit: int = 10) -> list:
    """
    搜索股票
    
    支持:
    - 代码精确/模糊匹配 (600, 600519)
    - 名称模糊匹配 (茅台, 贵州)
    - 拼音全拼匹配 (maotai, guizhoumaotai)
    - 拼音首字母匹配 (mt, gzmt)
    
    Args:
        query: 搜索关键词
        stock_list_df: 股票列表 DataFrame
        limit: 返回结果数量限制
    
    Returns:
        匹配的股票列表
    """
    query = query.strip().lower()
    
    if not query:
        return HOT_STOCKS[:limit]
    
    # 转换为可哈希的元组用于缓存
    stock_tuple = tuple(stock_list_df[["code", "name"]].itertuples(index=False, name=None))
    
    # 构建索引
    indexed = build_search_index(stock_tuple)
    
    results = []
    seen_codes = set()
    
    # 1. 代码精确匹配（优先级最高）
    code_exact = indexed[indexed["code"] == query.zfill(6)]
    for _, row in code_exact.iterrows():
        if row["code"] not in seen_codes:
            results.append({"code": row["code"], "name": row["name"], "match": "code_exact"})
            seen_codes.add(row["code"])
    
    # 2. 代码前缀匹配
    if len(results) < limit:
        code_prefix = indexed[indexed["code"].str.startswith(query)]
        for _, row in code_prefix.iterrows():
            if row["code"] not in seen_codes:
                results.append({"code": row["code"], "name": row["name"], "match": "code_prefix"})
                seen_codes.add(row["code"])
                if len(results) >= limit:
                    break
    
    # 3. 名称精确包含
    if len(results) < limit:
        name_contains = indexed[indexed["name"].str.contains(query, na=False, regex=False)]
        for _, row in name_contains.iterrows():
            if row["code"] not in seen_codes:
                results.append({"code": row["code"], "name": row["name"], "match": "name"})
                seen_codes.add(row["code"])
                if len(results) >= limit:
                    break
    
    # 4. 拼音首字母匹配
    if len(results) < limit:
        pinyin_init = indexed[indexed["pinyin_initials"].str.startswith(query)]
        for _, row in pinyin_init.iterrows():
            if row["code"] not in seen_codes:
                results.append({"code": row["code"], "name": row["name"], "match": "pinyin_init"})
                seen_codes.add(row["code"])
                if len(results) >= limit:
                    break
    
    # 5. 拼音全拼匹配
    if len(results) < limit:
        pinyin_full = indexed[indexed["pinyin_full"].str.contains(query, na=False, regex=False)]
        for _, row in pinyin_full.iterrows():
            if row["code"] not in seen_codes:
                results.append({"code": row["code"], "name": row["name"], "match": "pinyin_full"})
                seen_codes.add(row["code"])
                if len(results) >= limit:
                    break
    
    # 6. 代码模糊包含
    if len(results) < limit:
        code_contains = indexed[indexed["code"].str.contains(query, na=False)]
        for _, row in code_contains.iterrows():
            if row["code"] not in seen_codes:
                results.append({"code": row["code"], "name": row["name"], "match": "code"})
                seen_codes.add(row["code"])
                if len(results) >= limit:
                    break
    
    # 移除 match 字段返回
    return [{"code": r["code"], "name": r["name"]} for r in results[:limit]]


def get_hot_stocks() -> list:
    """获取热门股票列表"""
    return HOT_STOCKS
