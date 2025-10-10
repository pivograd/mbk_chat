import time
from typing import Optional, Dict, Any, Iterable, Tuple
from urllib.parse import urlparse
import urllib
import requests
import logging
import random

# =========================
# Конфиг по умолчанию
# =========================
DEFAULT_TIMEOUT = 60
MAX_RETRIES_503 = 20
MAX_RETRIES_429 = 8
INITIAL_BACKOFF = 0.5  # seconds
BACKOFF_FACTOR = 1.5   # exponential
MAX_BACKOFF = 15.0     # cap seconds

# =========================
# Логгер (опционально)
# =========================
logger = logging.getLogger("bitrix.api")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] %(name)s: %(message)s'))
    logger.addHandler(_h)

# =========================
# Исключения (совместимые)
# =========================
class ConnectionToBitrixError(Exception):
    pass

class BitrixTimeout(Exception):
    def __init__(self, requests_timeout: Exception, timeout: Optional[float]):
        super().__init__(f"Requests timeout: {requests_timeout}; configured timeout={timeout}")
        self.requests_timeout = requests_timeout
        self.timeout = timeout

class BitrixApiServerError(Exception):
    def __init__(self, has_resp: bool, json_response: Optional[dict], status_code: int, message: str = ""):
        super().__init__(message or f"Bitrix API error: status={status_code}")
        self.has_resp = has_resp
        self.json_response = json_response
        self.status_code = status_code

# =========================
# Утилиты
# =========================
def force_str(s, encoding='utf-8', errors='replace'):
    if isinstance(s, str):
        return s
    if isinstance(s, bytes):
        return s.decode(encoding, errors)
    return str(s)

def _mask_params_for_log(data_bytes: bytes) -> str:
    """
    Маскирует auth/webhook-ключи в строке параметров перед логированием.
    """
    txt = force_str(data_bytes)
    # простая маскировка auth=xxx
    txt = re_sub(r'(auth=)([^&]+)', r'\1***', txt)
    # webhook ключи в URL мы маскируем отдельно (см. ниже)
    return txt

def _mask_url_for_log(url: str) -> str:
    # https://domain/rest/{HOOK}/{METHOD}.json
    # Маскируем компонент HOOK (вид "123/abcdef...") оставляя только префикс.
    parts = url.split("/rest/")
    if len(parts) != 2:
        return url
    left, right = parts
    segs = right.split("/")
    if len(segs) >= 2:
        hook = segs[0]
        masked = hook[:3] + "***"
        segs[0] = masked
        return left + "/rest/" + "/".join(segs)
    return url

def re_sub(pattern: str, repl: str, text: str) -> str:
    import re
    return re.sub(pattern, repl, text)

class RawStringParam:
    def __init__(self, value):
        self.value = value
    __unicode__ = __str__ = lambda self: self.value
    __repr__ = lambda self: '<RawStringParam %r>' % self.value

def convert_params(form_data):
    def recursive_traverse(values, key=None):
        collection_t = (dict, list, tuple)
        list_like_t = (list, tuple)
        params = []

        if not isinstance(values, collection_t):
            values = '' if values is None else values
            if not isinstance(values, RawStringParam):
                values = urllib.parse.quote(force_str(values))
            else:
                values = str(values)
            return f'{key}={values}'

        if key is not None and isinstance(values, collection_t) and not values:
            return f'{key}[]='

        if isinstance(values, list_like_t):
            iterable = enumerate(values)
        elif isinstance(values, dict):
            iterable = values.items()
        else:
            raise TypeError(values)

        for inner_key, v in iterable:
            inner_key = urllib.parse.quote(force_str(inner_key))
            if key is not None:
                inner_key = f'{key}[{inner_key}]'
            result = recursive_traverse(v, inner_key)
            if isinstance(result, list):
                params.append('&'.join(result))
            else:
                params.append(result)

        return params

    return '&'.join(recursive_traverse(form_data))

# =========================
# HTTP вызов с ретраями
# =========================
def call_with_retries(
    url: str,
    converted_params: bytes,
    *,
    timeout: Optional[float] = DEFAULT_TIMEOUT,
    files=None,
    verify_ssl: bool = True,
    basic_auth=None,
    session: Optional[requests.Session] = None,
    logger_enabled: bool = True,
) -> requests.Response:
    s = session or requests.Session()

    retries_503 = MAX_RETRIES_503
    retries_429 = MAX_RETRIES_429
    backoff = INITIAL_BACKOFF

    while True:
        try:
            response = s.post(
                url,
                converted_params,
                auth=basic_auth,
                timeout=timeout,
                files=files,
                allow_redirects=False,
                verify=verify_ssl,
                headers={"Content-Type": "application/x-www-form-urlencoded"} if not files else None,
            )
        except (requests.ConnectionError, requests.exceptions.SSLError) as e:
            raise ConnectionToBitrixError() from e
        except requests.Timeout as e:
            raise BitrixTimeout(e, timeout=timeout) from e

        # Nginx 403
        if response.status_code == 403 and 'nginx' in response.text.lower():
            raise BitrixApiServerError(
                has_resp=False,
                json_response={'error': 'Nginx 403 Forbidden', 'error_description': 'Nginx 403 Forbidden'},
                status_code=response.status_code,
                message='Nginx 403 Forbidden',
            )

        # Битрикс 500 без JSON
        if response.status_code == 500 and response.text.strip() == 'Internal Server Error':
            raise BitrixApiServerError(
                has_resp=False,
                json_response={'error': 'Bitrix 500 Internal Server Error', 'error_description': 'Bitrix 500 Internal Server Error'},
                status_code=response.status_code,
                message='Bitrix 500 Internal Server Error',
            )

        # 503 — повтор
        if response.status_code == 503 and retries_503 > 0:
            if logger_enabled:
                logger.debug("503 from Bitrix, retrying: url=%s, left=%d", _mask_url_for_log(url), retries_503)
            time.sleep(backoff + random.uniform(0, 0.2))
            retries_503 -= 1
            backoff = min(backoff * BACKOFF_FACTOR, MAX_BACKOFF)
            continue
        elif response.status_code == 503 and retries_503 <= 0:
            if logger_enabled:
                logger.warning("503 retries exhausted: url=%s", _mask_url_for_log(url))

        # 429 — Too Many Requests
        if response.status_code == 429 and retries_429 > 0:
            retry_after = response.headers.get("Retry-After")
            delay = None
            if retry_after:
                try:
                    delay = float(retry_after)
                except ValueError:
                    delay = None
            if delay is None:
                delay = backoff
                backoff = min(backoff * BACKOFF_FACTOR, MAX_BACKOFF)
            if logger_enabled:
                logger.debug("429 rate limited, sleeping %.2fs, left=%d", delay, retries_429)
            time.sleep(delay)
            retries_429 -= 1
            continue

        # 301/302 — возможная смена домена
        if response.status_code in (301, 302):
            location = response.headers.get('location')
            if location:
                old_domain = urlparse(url).netloc
                new_domain = urlparse(location).netloc
                if old_domain != new_domain and logger_enabled:
                    logger.debug("Redirect domain change: %s -> %s", old_domain, new_domain)
                # повторим запрос по новому адресу (без сброса счётчиков ретраев)
                url = location
                continue
            if logger_enabled:
                logger.warning("Redirect without Location header: url=%s", _mask_url_for_log(url))

        return response

# =========================
# Публичный API
# =========================
def api_call(domain, api_method, auth_token, params=None, webhook=False, timeout=DEFAULT_TIMEOUT,
             *, verify_ssl: bool = True, basic_auth=None, session: Optional[requests.Session] = None, log_io: bool = False):
    """
    POST-запрос к Bitrix24 API.
    """
    params = params or {}
    hook_key = ''
    if webhook:
        hook_key = f'{auth_token}/'
    else:
        params['auth'] = auth_token

    converted_params = convert_params(params).encode('utf-8')
    url = f'https://{domain}/rest/{hook_key}{api_method}.json'

    t0 = time.time()
    if log_io:
        logger.info('bitrix_request %s %s', t0, _mask_url_for_log(url))
        logger.debug('bitrix_request_body %s %s', t0, _mask_params_for_log(converted_params))

    resp = call_with_retries(
        url,
        converted_params,
        timeout=timeout,
        files=None,
        verify_ssl=verify_ssl,
        basic_auth=basic_auth,
        session=session,
        logger_enabled=log_io
    )

    if api_method != 'batch':
        try:
            data = resp.json()
            data_time = data.get('time')
            if data_time:
                operating = data_time.get('operating', 0)
                if operating > 300:
                    # INFO для 300–400, WARNING для 400+
                    (logger.info if operating < 400 else logger.warning)(
                        'method_operating: %s %s operating=%s', domain, api_method, operating
                    )
        except Exception as e:
            logger.warning('method_operating_exception: %r', e)

    if log_io:
        try:
            logger.info('bitrix_response %s %s', t0, force_str(resp.text).encode().decode('unicode_escape'))
        except Exception:
            logger.info('bitrix_response %s %s', t0, resp.text[:2000])  # ограничим объём

    return resp
