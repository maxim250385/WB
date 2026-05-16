import re

# Граница русской части — подпись команды, после неё идёт английский перевод
_FOOTER_MARKER = 'С уважением, команда WB API'


def extract_hashtags(text: str) -> list[str]:
    """Хэштеги всегда в первых строках сообщения."""
    first_lines = text.split('\n\n')[0]
    return re.findall(r'#\w+', first_lines)


def extract_russian_text(text: str) -> str:
    """Вырезает русскую часть, убирая футер и английский перевод."""
    idx = text.find(_FOOTER_MARKER)
    if idx != -1:
        text = text[:idx]
    return text.strip()


def extract_endpoints(text: str) -> list[tuple[str, str]]:
    """Извлекает все упомянутые API-endpoints в виде (метод, путь)."""
    return re.findall(r'\b(GET|POST|PUT|DELETE|PATCH)\s+(/[\w/{}.\-]+)', text)
