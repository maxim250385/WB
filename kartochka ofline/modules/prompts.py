# =============================================================================
#  modules/prompts.py — Промпты для Gemini и схемы полей по категориям
# =============================================================================

# ---------------------------------------------------------------------------
# БАЗОВЫЕ ПОЛЯ
# ---------------------------------------------------------------------------
BASE_FIELDS: list[str] = [
    "article_supplier",
    "name",
    "category",
    "brand",
    "country_of_origin",
    "length_cm",
    "width_cm",
    "height_cm",
    "weight_kg",
    "description",
    "complectation",
    "tnved",
    "barcode",
    "warranty_months",
]

# ---------------------------------------------------------------------------
# ДОПОЛНИТЕЛЬНЫЕ ПОЛЯ ПО КАТЕГОРИЯМ
# ---------------------------------------------------------------------------
CATEGORY_EXTRA_FIELDS: dict[str, list[str]] = {
    "одежда": [
        "material_composition",
        "sizes_available",
        "color",
        "gender",
        "season",
        "care_instructions",
        "style",
    ],
    "обувь": [
        "material_upper",
        "material_sole",
        "material_lining",
        "sizes_available",
        "color",
        "gender",
        "season",
        "heel_height_cm",
    ],
    "электроника": [
        "power_w",
        "voltage_v",
        "battery_type",
        "battery_capacity_mah",
        "connectivity",
        "color",
        "model_number",
        "os",
        "display_inches",
        "memory_gb",
        "processor",
        "camera_mp",
    ],
    "бытовая техника": [
        "power_w",
        "voltage_v",
        "energy_class",
        "color",
        "model_number",
        "noise_db",
        "capacity_l",
        "spin_rpm",           # Для стиральных машин
        "max_load_kg",        # Максимальная загрузка
        "wash_programs",      # Количество программ стирки
        "water_consumption_l", # Расход воды
        "features",
    ],
    "мебель": [
        "material_main",
        "material_finish",
        "color",
        "load_capacity_kg",
        "assembly_required",
        "dimensions_assembled",
        "style_interior",
    ],
    "товары для дома": [
        "material_main",
        "color",
        "volume_l",
        "style_interior",
        "power_w",
        "features",
        "certification",
    ],
    "косметика": [
        "volume_ml",
        "skin_type",
        "active_ingredients",
        "shelf_life_months",
        "certification",
        "gender",
        "application_method",
        "effect",
    ],
    "красота и здоровье": [
        "volume_ml",
        "skin_type",
        "active_ingredients",
        "shelf_life_months",
        "certification",
        "gender",
        "application_method",
        "effect",
        "power_w",
        "voltage_v",
    ],
    "игрушки": [
        "age_from_years",
        "material_main",
        "color",
        "certification",
        "battery_required",
        "dimensions_cm",
        "developing_skills",
    ],
    "детские товары": [
        "age_from_years",
        "material_main",
        "color",
        "certification",
        "battery_required",
        "dimensions_cm",
        "developing_skills",
        "sizes_available",
        "gender",
    ],
    "продукты питания": [
        "volume_ml",
        "shelf_life_days",
        "storage_conditions",
        "composition",
        "calories_per_100g",
        "proteins_per_100g",
        "fats_per_100g",
        "carbs_per_100g",
        "allergens",
        "certification",
    ],
    "автотовары": [
        "compatible_brands",        # Совместимые марки авто
        "compatible_models",        # Совместимые модели
        "compatible_years",         # Годы выпуска авто
        "material_main",
        "color",
        "model_number",
        "installation_complexity",  # Сложность установки (простая/средняя/специалист)
        "power_w",
        "voltage_v",
        "connector_type",           # Тип разъёма/подключения
        "features",
        "certification",
    ],
    "туризм и рыбалка": [
        "material_main",
        "color",
        "max_load_kg",
        "dimensions_packed",        # Размеры в сложенном виде
        "dimensions_assembled",     # Размеры в разложенном виде
        "season",
        "waterproof",               # Водонепроницаемость (да/нет/степень защиты)
        "temperature_min_c",        # Минимальная рабочая температура
        "features",
        "certification",
        "gender",
        "age_from_years",
        # Рыболовное специфичное
        "fishing_type",             # Вид рыбалки (спиннинг, фидер, поплавочная)
        "test_g",                   # Тест приманки, г (для удилищ)
        "length_m",                 # Длина, м (для удилищ, лески)
        "breaking_strength_kg",     # Разрывная нагрузка, кг (для лески/шнура)
        "gear_ratio",               # Передаточное число (для катушек)
    ],
    "спорт": [
        "material_main",
        "color",
        "sizes_available",
        "gender",
        "max_load_kg",
        "age_from_years",
        "features",
        "certification",
    ],
    "другое": [],
}

DEFAULT_CATEGORY = "другое"

# ---------------------------------------------------------------------------
# СИСТЕМНЫЙ ПРОМПТ
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """Ты — ассистент для заполнения карточек товаров на маркетплейсах Wildberries и Ozon.
Твоя задача: извлечь из текста поставщика СУХИЕ ТЕХНИЧЕСКИЕ ФАКТЫ и вернуть их строго в формате JSON.

ПРАВИЛА:
1. Отвечай ТОЛЬКО валидным JSON-объектом. Без текста до/после. Без markdown-блоков (``` ).
2. Если информации для поля нет — ставь null. Не пустую строку, именно null.
3. НЕ придумывай данные. Только то, что явно указано в тексте.
4. НЕ пиши рекламных описаний — только сухие технические факты.
5. Числа пиши как числа: 12.5, не "12.5 кг".
6. Текстовые значения на русском языке.

ОПРЕДЕЛЕНИЕ КАТЕГОРИИ (поле "category"):
Определяй точно по содержанию товара. Примеры:
- Стиральная машина, холодильник, пылесос, утюг → "бытовая техника"
- Телефон, ноутбук, наушники, планшет → "электроника"
- Футболка, куртка, платье → "одежда"
- Кроссовки, ботинки, сандалии → "обувь"
- Диван, шкаф, кровать, стол → "мебель"
- Палатка, спальник, удочка, катушка, леска → "туризм и рыбалка"
- Масло моторное, автомагнитола, коврики в авто → "автотовары"
- Крем, шампунь, помада, сыворотка → "косметика"
- Игрушка, конструктор, кукла → "игрушки"
- Продукты, еда, напитки → "продукты питания"
НИКОГДА не определяй стиральную машину как "одежда"."""

SYSTEM_PROMPT_VISION = """Ты — ассистент для заполнения карточек товаров на маркетплейсах Wildberries и Ozon.
На изображении показан товар, его упаковка или этикетка.
Извлеки все видимые технические характеристики, текст с этикетки, артикулы, штрихкоды, состав.
Верни данные строго в формате JSON без markdown-блоков. Для отсутствующих полей — null.
Определяй категорию точно по содержанию товара — не по упаковке или фону."""


def build_extraction_prompt(raw_text: str, fields: list[str]) -> str:
    """Строит user-промпт для извлечения конкретных полей."""
    # Обрезаем слишком длинный текст — Gemini имеет лимит токенов
    max_chars = 30_000
    if len(raw_text) > max_chars:
        raw_text = raw_text[:max_chars] + "\n\n[... текст обрезан до 30 000 символов ...]"

    fields_block = "\n".join(f'  "{f}": null' for f in fields)
    return f"""Извлеки данные из текста и верни JSON. Для отсутствующих данных используй null.

ПОЛЯ:
{{
{fields_block}
}}

ТЕКСТ ПОСТАВЩИКА:
\"\"\"
{raw_text}
\"\"\"

Верни только JSON-объект."""
