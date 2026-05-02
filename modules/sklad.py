import time
import random

from .storage import REGIONS, fetch_json, new_session


class WBParser:
    def __init__(self, session=None):
        self.session = session if session is not None else new_session()
        self.regions = REGIONS

    def get_stock_data(self, articles):
        """Строки остатков по регионам и размерам."""
        results = []

        for art in articles:
            print(f"[*] Проверяю артикул: {art}")
            for reg in self.regions:
                api_url = (
                    f"https://card.wb.ru/cards/v4/detail"
                    f"?appType=1&curr=rub&dest={reg['id']}&nm={art}"
                )
                data, err = fetch_json(self.session, api_url, timeout=15, attempts=3)
                if err == "bad_request":
                    pass
                elif err is not None:
                    if isinstance(err, Exception):
                        print(f"  [!] Ошибка парсинга {art} / {reg['name']}: {err}")
                    else:
                        print(f"  [!] Ошибка парсинга {art} / {reg['name']}: {err}")
                elif data is not None:
                    products = data.get("products", [])
                    if products:
                        for size in products[0].get("sizes", []):
                            qty = sum(s.get("qty", 0) for s in size.get("stocks", []))
                            results.append({
                                "Артикул": art,
                                "Регион":  reg["name"],
                                "Размер":  size.get("origName", "Единый"),
                                "Остаток": qty,
                            })

                time.sleep(random.uniform(0.5, 1.0))

        return results
