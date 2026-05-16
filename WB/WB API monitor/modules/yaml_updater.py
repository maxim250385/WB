import os
import re
import json
import logging
from pathlib import Path
from datetime import date
from modules.gemini_client import ask_gemini_json

# ─── Документация WB API ──────────────────────────────────
# modules/ → WB API monitor/ → WB/ → WB API Документация/
DOCS_DIR = str(Path(__file__).parent.parent.parent / 'WB API Документация')

# ─── Отложенные изменения ─────────────────────────────────
_PENDING_FILE = Path(__file__).parent.parent / 'data' / 'pending_changes.json'

HASHTAG_TO_YAML: dict[str, str] = {
    # Работа с товарами
    '#работа_с_товарами':        '02-products.yaml',
    '#product_management':       '02-products.yaml',
    '#items':                    '02-products.yaml',
    # Заказы FBS
    '#заказы_fbs':               '03-orders-fbs.yaml',
    '#orders_fbs':               '03-orders-fbs.yaml',
    '#fbs':                      '03-orders-fbs.yaml',
    # Заказы DBW
    '#заказы_dbw':               '04-orders-dbw.yaml',
    '#orders_dbw':               '04-orders-dbw.yaml',
    '#dbw':                      '04-orders-dbw.yaml',
    # Заказы DBS
    '#заказы_dbs':               '05-orders-dbs.yaml',
    '#orders_dbs':               '05-orders-dbs.yaml',
    '#dbs':                      '05-orders-dbs.yaml',
    # Самовывоз
    '#заказы_самовывоз':         '06-in-store-pickup.yaml',
    '#orders_in_store_pickup':   '06-in-store-pickup.yaml',
    '#in_store_pickup':          '06-in-store-pickup.yaml',
    '#pickup':                   '06-in-store-pickup.yaml',
    # Поставки FBW
    '#поставки_fbw':             '07-orders-fbw.yaml',
    '#fbw_supplies':             '07-orders-fbw.yaml',
    '#fbw':                      '07-orders-fbw.yaml',
    # Продвижение
    '#маркетинг_и_продвижение':  '08-promotion.yaml',
    '#marketing_and_promotions': '08-promotion.yaml',
    '#promotion':                '08-promotion.yaml',
    # Коммуникации
    '#общение_с_покупателями':   '09-communications.yaml',
    '#customer_communication':   '09-communications.yaml',
    '#communication':            '09-communications.yaml',
    # Тарифы
    '#тарифы':                   '10-tariffs.yaml',
    '#tariffs':                  '10-tariffs.yaml',
    # Аналитика
    '#аналитика_и_данные':       '11-analytics.yaml',
    '#analytics_and_data':       '11-analytics.yaml',
    '#analytics':                '11-analytics.yaml',
    # Отчёты
    '#отчёты':                   '12-reports.yaml',
    '#reports':                  '12-reports.yaml',
    # Финансы / документы
    '#документы_и_бухгалтерия':  '13-finances.yaml',
    '#documents_and_accounting': '13-finances.yaml',
    '#finances':                 '13-finances.yaml',
    # Общее
    '#общее':                    '01-general.yaml',
    '#general':                  '01-general.yaml',
}

logger = logging.getLogger(__name__)

_FORCE_INSTRUCTION = (
    '\nВАЖНО: Это отложенное изменение — дата вступления в силу уже наступила. '
    'Используй action="modify" и применяй changes немедленно. action="schedule" запрещён.'
)

_PROMPT = """\
Ты обновляешь документацию WB API в формате OpenAPI YAML.

УВЕДОМЛЕНИЕ ОБ ИЗМЕНЕНИИ API:
---
{message}
---

ТЕКУЩИЙ YAML РАЗДЕЛ (файл: {yaml_file}):
---
{yaml_section}
---

Проанализируй изменение и верни JSON строго в этом формате:
{{
  "action": "modify" | "add" | "deprecate" | "schedule" | "none",
  "apply_date": "YYYY-MM-DD",
  "summary": "краткое описание изменения на русском (1-2 предложения)",
  "changes": [
    {{
      "find": "точный текст из YAML для поиска включая отступы",
      "replace": "текст замены с теми же отступами"
    }}
  ]
}}

Правила:
- action="modify" — изменились параметры/поля существующего метода и изменение уже активно
- action="add" — новый метод которого нет в YAML; в find укажи последнюю строку раздела как якорь, в replace — эту же строку плюс новый блок метода после неё
- action="deprecate" — метод устаревает или отключается; добавь deprecated: true и x-deprecated-info с датой и причиной
- action="schedule" — поведение существующего метода изменится в конкретную будущую дату; укажи apply_date (YYYY-MM-DD) и подготовь changes как для modify, но сейчас к YAML не применять
- action="none" — изменение не требует правки YAML (технические работы, анонсы без структурных изменений, напоминания)
- apply_date заполняй только для action="schedule", для остальных — пустая строка
- В "find" указывай ТОЧНЫЙ текст из YAML как он есть, с отступами
- Сохраняй YAML-форматирование и отступы
- Если секция не найдена и это не новый метод — верни action="none" с пояснением в summary
{force_instruction}"""


def _load_pending() -> list:
    try:
        with open(_PENDING_FILE, encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_pending(records: list):
    with open(_PENDING_FILE, 'w', encoding='utf-8') as f:
        json.dump(records, f, indent=2, ensure_ascii=False)


def _schedule_change(apply_date: str, hashtag: str, message_text: str,
                     endpoints: list, summary: str, changes: list):
    records = _load_pending()
    records.append({
        'apply_date': apply_date,
        'yaml_file': HASHTAG_TO_YAML.get(hashtag, ''),
        'hashtag': hashtag,
        'message': message_text,
        'endpoints': endpoints,
        'summary': summary,
        'changes': changes,
        'status': 'pending',
        'created_at': date.today().isoformat(),
        'applied_at': None,
    })
    _save_pending(records)
    logger.info(f'Изменение запланировано на {apply_date}: {summary}')


def get_due_pending() -> list:
    """Возвращает pending-записи с apply_date <= сегодня."""
    today = date.today().isoformat()
    return [r for r in _load_pending()
            if r.get('status') == 'pending' and r.get('apply_date', '9999') <= today]


def mark_pending_applied(record: dict):
    records = _load_pending()
    for r in records:
        if (r.get('apply_date') == record['apply_date'] and
                r.get('hashtag') == record['hashtag'] and
                r.get('created_at') == record['created_at'] and
                r.get('status') == 'pending'):
            r['status'] = 'applied'
            r['applied_at'] = date.today().isoformat()
            r['notified'] = False
            break
    _save_pending(records)


def get_applied_unnotified() -> list:
    """Возвращает applied-записи, по которым ещё не отправлено уведомление."""
    return [r for r in _load_pending()
            if r.get('status') == 'applied' and not r.get('notified', False)]


def mark_pending_notified(record: dict):
    records = _load_pending()
    for r in records:
        if (r.get('apply_date') == record['apply_date'] and
                r.get('hashtag') == record['hashtag'] and
                r.get('created_at') == record['created_at'] and
                r.get('status') == 'applied'):
            r['notified'] = True
            break
    _save_pending(records)


def _get_yaml_path(hashtag: str) -> str | None:
    yaml_file = HASHTAG_TO_YAML.get(hashtag)
    if not yaml_file:
        return None
    return os.path.join(DOCS_DIR, yaml_file)


def _find_section(yaml_text: str, endpoints: list[tuple[str, str]]) -> str:
    """
    Извлекает из YAML раздел для указанных endpoints.
    Если endpoint не найден — возвращает конец файла (контекст для добавления нового метода).
    Если endpoints не указаны — возвращает первые 150 строк как общий контекст.
    """
    if not endpoints:
        return '\n'.join(yaml_text.splitlines()[:150])

    sections = []
    not_found = []

    for method, path in endpoints:
        pattern = re.compile(r'^( +)(' + re.escape(path) + r')\s*:', re.MULTILINE)
        match = pattern.search(yaml_text)
        if not match:
            not_found.append(f'{method} {path}')
            continue

        start = match.start()
        indent = len(match.group(1))
        # Следующий path на том же уровне отступа
        next_path = re.compile(r'^ {' + str(indent) + r'}/\S', re.MULTILINE)
        next_match = next_path.search(yaml_text, match.end())
        end = next_match.start() if next_match else len(yaml_text)
        sections.append(yaml_text[start:end].rstrip())

    if not_found:
        # Новые методы — отдаём последние 80 строк как контекст для вставки
        tail = '\n'.join(yaml_text.splitlines()[-80:])
        sections.append(f'# Endpoint не найден в YAML (новый метод): {", ".join(not_found)}\n{tail}')

    return '\n\n'.join(sections)


def _apply_changes(yaml_text: str, changes: list[dict]) -> tuple[str, int]:
    """Применяет список замен. Возвращает (обновлённый текст, количество применённых замен)."""
    applied = 0
    for change in changes:
        find = change.get('find', '')
        replace = change.get('replace', '')
        if not find:
            continue
        if find in yaml_text:
            yaml_text = yaml_text.replace(find, replace, 1)
            applied += 1
            logger.info(f'Применена замена: {find[:60].strip()}...')
        else:
            logger.warning(f'Фрагмент не найден в YAML: {find[:80].strip()}')
    return yaml_text, applied


def process_message_for_yaml(
    message_text: str,
    hashtag: str,
    endpoints: list[tuple[str, str]],
    force: bool = False,
) -> str | None:
    """
    Обрабатывает сообщение для одного YAML файла.
    Возвращает строку-summary если файл был обновлён, иначе None.
    """
    yaml_path = _get_yaml_path(hashtag)
    if not yaml_path or not os.path.exists(yaml_path):
        logger.warning(f'YAML не найден для хэштега {hashtag}: {yaml_path}')
        return None

    yaml_file = os.path.basename(yaml_path)
    with open(yaml_path, 'r', encoding='utf-8') as f:
        yaml_text = f.read()

    yaml_section = _find_section(yaml_text, endpoints)

    prompt = _PROMPT.format(
        message=message_text,
        yaml_file=yaml_file,
        yaml_section=yaml_section,
        force_instruction=_FORCE_INSTRUCTION if force else '',
    )

    logger.info(f'Gemini анализирует {yaml_file}{"[force]" if force else ""}...')
    result = ask_gemini_json(prompt)
    if not result:
        logger.error(f'Gemini не ответил для {yaml_file}')
        return '!error'

    action  = result.get('action', 'none')
    summary = result.get('summary', '')
    changes = result.get('changes', [])

    if action == 'none':
        logger.info(f'{yaml_file}: правки не нужны — {summary}')
        return None

    if action == 'schedule':
        apply_date = result.get('apply_date', '')
        if apply_date and changes:
            _schedule_change(apply_date, hashtag, message_text, endpoints, summary, changes)
            return f'[schedule:{apply_date}] {summary}'
        logger.warning(f'{yaml_file}: action=schedule но нет apply_date или changes')
        return None

    if not changes:
        logger.warning(f'{yaml_file}: action={action} но changes пустой')
        return None

    updated, applied = _apply_changes(yaml_text, changes)
    if applied == 0:
        logger.warning(f'{yaml_file}: ни одна замена не применена')
        return None

    with open(yaml_path, 'w', encoding='utf-8') as f:
        f.write(updated)

    logger.info(f'{yaml_file}: обновлён ({action}, {applied} замен)')
    return f'[{yaml_file}] {action}: {summary}'
