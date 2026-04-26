# =============================================================================
#  modules/validator.py — Валидация полей
# =============================================================================
import re

REQUIRED_FIELDS = {
    "name", "category", "country_of_origin",
    "weight_kg", "length_cm", "width_cm", "height_cm",
}
MISSING_LABEL = "Уточнить у поставщика"

NUMERIC_FIELDS = {
    "length_cm", "width_cm", "height_cm", "weight_kg",
    "power_w", "voltage_v", "battery_capacity_mah",
    "heel_height_cm", "volume_ml", "volume_l", "shelf_life_months",
    "shelf_life_days", "age_from_years", "load_capacity_kg",
    "max_load_kg", "calories_per_100g", "noise_db", "capacity_l",
    "display_inches", "memory_gb", "warranty_months", "camera_mp",
    "spin_rpm", "wash_programs", "water_consumption_l",
    "temperature_min_c", "test_g", "length_m",
    "breaking_strength_kg", "gear_ratio",
}


def validate_and_fill(data: dict) -> tuple[dict, list[str]]:
    result   = {}
    warnings = []
    for field, value in data.items():
        cleaned = _clean_value(field, value)
        if cleaned is None or cleaned == "":
            if field in REQUIRED_FIELDS:
                result[field] = MISSING_LABEL
                warnings.append(f"'{field}'")
            else:
                result[field] = ""
        else:
            result[field] = cleaned
    return result, warnings


def _clean_value(field: str, value):
    if value is None:
        return None
    if field in NUMERIC_FIELDS:
        return _to_float(value)
    if isinstance(value, list):
        return ", ".join(str(v) for v in value if v is not None)
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else None
    return value


def _to_float(value) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        m = re.search(r"[\d]+[.,]?[\d]*", value.replace(",", "."))
        if m:
            try:
                return float(m.group().replace(",", "."))
            except ValueError:
                pass
    return None
