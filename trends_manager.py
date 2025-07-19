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

# متغيرات عالمية
trends_data = load_trends()
trend_indexes = load_indexes()

# دالة اختيار الترند حسب LIFO
def get_next_trend_lifo(category):
    trends = trends_data.get(category, [])
    if not trends:
        return None

    index = trend_indexes.get(category, len(trends) - 1)
    trend = trends[index]

    next_index = index - 1 if index > 0 else len(trends) - 1
    trend_indexes[category] = next_index

    save_indexes(trend_indexes)
    return trend

# دالة عامة تستخدم النوع "general" فقط
def get_general_trend():
    return get_next_trend_lifo("general")

# إعادة تعيين كل المؤشرات
def reset_trend_indexes():
    global trend_indexes
    trend_indexes = {}
    save_indexes(trend_indexes)
