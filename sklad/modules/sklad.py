import time
import random

from .storage import REGIONS, WH_NAMES, fetch_json, new_session


class WBParser:
    def __init__(self, session=None):
        self.session = session if session is not None else new_session()
        self.regions = REGIONS

    def get_stock_data(self, articles):
        """
        Остатки по складам. Обходим все регионы (dest), собираем
        уникальные записи (артикул, wh-склад, размер) — без двойного счёта.
        Один склад может обслуживать несколько регионов, поэтому первая
        увиденная запись для пары (артикул, wh, размер) побеждает.
        """
        # (art_str, wh_id, size_name) -> qty
        seen: dict[tuple, int] = {}

        for art in articles:
            print(f"[*] Проверяю артикул: {art}")
            for reg in self.regions:
                api_url = (
                    f"https://card.wb.ru/cards/v4/detail"
                    f"?appType=1&curr=rub&dest={reg['id']}&nm={art}"
                )
                data, err = fetch_json(self.session, api_url, timeout=15, attempts=5)

                if err is not None:
                    if err != "bad_request":
                        print(f"  [!] {art} / {reg['name']}: {err}")
                    time.sleep(random.uniform(0.5, 1.0))
                    continue

                products = (data or {}).get("products", [])
                if not products:
                    time.sleep(random.uniform(0.5, 1.0))
                    continue

                for size in products[0].get("sizes", []):
                    size_name = size.get("origName") or "Единый"
                    for stock in size.get("stocks", []):
                        wh_id = stock.get("wh")
                        qty   = stock.get("qty", 0)
                        if wh_id is None:
                            continue
                        key = (str(art), wh_id, size_name)
                        if key not in seen:
                            seen[key] = qty

                time.sleep(random.uniform(0.5, 1.0))

        results = []
        for (art, wh_id, size_name), qty in seen.items():
            wh_name = WH_NAMES.get(wh_id, f"Склад #{wh_id}")
            results.append({
                "Артикул": art,
                "Склад":   wh_name,
                "Размер":  size_name,
                "Остаток": qty,
            })
        return results
