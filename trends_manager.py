import json
import os

TRENDS_FILE = "trends_data.json"
INDEXES_FILE = "trend_indexes.json"

# تحميل الترندات
def load_trends():
    if not os.path.exists(TRENDS_FILE):
        return {}
    with open(TRENDS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# تحميل مؤشرات الترند
def load_indexes():
    if not os.path.exists(INDEXES_FILE):
        return {}
    with open(INDEXES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# حفظ المؤشرات
def save_indexes(indexes):
    with open(INDEXES_FILE, "w", encoding="utf-8") as f:
        json.dump(indexes, f, ensure_ascii=False, indent=2)

# متغيرات عالمية تحمل بيانات الترندات والمؤشرات
trends_data = load_trends()
trend_indexes = load_indexes()

# دالة اختيار الترند حسب LIFO (آخر ترند مُضاف أولاً)
def get_next_trend_lifo(group_type):
    trends = trends_data.get(group_type, [])
    if not trends:
        return None

    index = trend_indexes.get(group_type, len(trends) - 1)
    trend = trends[index]

    next_index = index - 1 if index > 0 else len(trends) - 1
    trend_indexes[group_type] = next_index

    save_indexes(trend_indexes)

    return trend

# دالة إعادة تعيين المؤشرات (reset)
def reset_trend_indexes():
    global trend_indexes
    trend_indexes = {}
    save_indexes(trend_indexes)
