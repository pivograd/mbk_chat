from typing import Optional, Union, Any, Tuple, List, Dict, Sequence
from collections import OrderedDict

from bx24.bx_utils.exceptions import CallListException

# какие методы возвращают список не напрямую, а в обёртке
METHOD_WRAPPERS: Dict[str, str] = {
    'tasks.task.list': 'tasks',
    'tasks.task.history.list': 'list',
    'tasks.task.getFields': 'fields',
    'tasks.task.getaccess': 'allowedActions',
    'sale.order.list': 'orders',
    'sale.propertyvalue.list': 'propertyValues',
    'sale.basketItem.list': 'basketItems',
    'crm.stagehistory.list': 'items',
    'crm.item.list': 'items',
    'crm.type.list': 'types',
    'crm.item.productrow.list': 'productRows',
    'userfieldconfig.list': 'fields',
    'catalog.catalog.list': 'catalogs',
    'catalog.product.list': 'products',
    'catalog.storeproduct.list': 'storeProducts',
    'catalog.product.offer.list': 'offers',
    'catalog.section.list': 'sections',
    'catalog.productPropertyEnum.list': 'productPropertyEnums',
    'rpa.item.list': 'items',
    'rpa.stage.listForType': 'stages',
    'socialnetwork.api.workgroup.list': 'workgroups',
    'catalog.product.sku.list': 'units',
}

WEIRD_PAGINATION_METHODS = {
    'task.item.list',
    'task.items.getlist',
    'task.elapseditem.getlist',
}

ALLOWABLE_TIME_MS = 2000  # только для возможного логирования при необходимости


class BatchResultDict(OrderedDict):
    """Контейнер результата для батча: { "0": {"result": <payload>} | {"error": {...}}, ... }"""
    @property
    def all_ok(self) -> bool:
        return all('error' not in part for part in self.values())

    @property
    def errors(self) -> Dict[str, Any]:
        return {k: v.get('error') for k, v in self.items() if 'error' in v}


def _unwrap_batch_res(batch_res: BatchResultDict,
                      result: Union[list, dict, None] = None,
                      wrapper: Optional[str] = None) -> Union[list, dict]:
    """
    Склеивает результаты батча в общий список/обёртку.
    Если batch_res пуст — возвращает переданный result как есть.
    """
    if not batch_res.all_ok:
        raise CallListException(batch_res.errors)

    if result is None:
        result = {wrapper: []} if wrapper else []

    for part in batch_res.values():
        chunk = part['result'][wrapper] if wrapper else part['result']
        (result[wrapper] if wrapper else result).extend(chunk)

    return result


def _next_params(method: str, params: dict, next_step: int, page_size: int = 50) -> dict:
    """Параметры следующей страницы. Для «странных» методов — особая логика."""
    m = method.lower()
    if m not in WEIRD_PAGINATION_METHODS:
        return dict(params or {}, start=next_step)

    i_num_page = next_step // page_size + 1
    nav_params = OrderedDict([('nPageSize', page_size), ('iNumPage', i_num_page)])

    if not isinstance(params, OrderedDict):
        params = OrderedDict(params or {})
    else:
        params = params.copy()

    params.pop('PARAMS', None)

    def _cnt(opt=0):  # количество «обязательных» с учётом опционального первого
        return len(params) - opt

    if m == 'task.item.list':
        if _cnt() < 1:
            params['ORDER'] = {}
        if _cnt() < 2:
            params['FILTER'] = {}
        if _cnt() > 3:
            raise ValueError('task.item.list: слишком много параметров. Допустимо ORDER, FILTER, SELECT.')
        select = None
        if _cnt() == 3:
            _, select = params.popitem()
        params['PARAMS'] = {'NAV_PARAMS': nav_params}
        if select is not None:
            params['SELECT'] = select
        return params

    if m == 'task.items.getlist':
        if _cnt() < 1:
            params['ORDER'] = {'ID': 'asc'}
        if _cnt() < 2:
            params['FILTER'] = {}
        if _cnt() < 3:
            params['TASKDATA'] = ['ID', 'TITLE']
        while _cnt() > 3:
            params.popitem()
        params['NAV_PARAMS'] = {'NAV_PARAMS': nav_params}
        return params

    # task.elapseditem.getlist
    opt = 1 if (params and isinstance(next(iter(params.values())), (int, str))) else 0
    if _cnt(opt) < 1:
        params['ORDER'] = {'ID': 'ASC'}
    if _cnt(opt) < 2:
        params['FILTER'] = {}
    if _cnt(opt) < 3:
        params['SELECT'] = ['*']
    while _cnt(opt) > 3:
        params.popitem()
    params['PARAMS'] = {'NAV_PARAMS': nav_params}
    return params


def _check_params(method: str, params: Any) -> Any:
    if method.lower() == 'task.ctasks.getlist':
        raise ValueError('task.ctasks.getlist не поддерживает пагинацию в облаке. Используйте tasks.task.list')
    if isinstance(params, (list, tuple)):
        params = OrderedDict((str(i), value) for i, value in enumerate(params))
    return params


def _build_batch_cmd(method: str, params: Optional[dict], build_query: callable) -> str:
    """
    Строит строку команды для REST batch: "method?key=value&arr[]=1..."
    :param build_query: функция, аналогичная convert_params, которая вернёт строку query без ведущего '?'
    """
    if not params:
        return method
    return f"{method}?{build_query(params)}"


def _do_rest_batch(bx_token,
                   methods: Sequence[Tuple[str, Optional[dict]]],
                   *,
                   timeout: Optional[int],
                   chunk_size: int,
                   build_query: callable) -> BatchResultDict:
    """
    Выполняет REST-батчи через bx_token.call_api_method('batch', ...), разбивая по chunk_size (<=50).
    Возвращает BatchResultDict совместимый с _unwrap_batch_res().
    """
    assert 1 <= chunk_size <= 50
    br = BatchResultDict()
    idx_global = 0

    for i in range(0, len(methods), chunk_size):
        chunk = methods[i:i + chunk_size]
        key_order: List[str] = []
        cmd_payload: Dict[str, str] = {}

        for j, (m, p) in enumerate(chunk):
            key = f'c{j}'
            key_order.append(key)
            cmd_payload[key] = _build_batch_cmd(m, p, build_query)

        batch = bx_token.call_api_method(
            'batch',
            params={'halt': 1, 'cmd': cmd_payload},
            timeout=timeout
        )

        if isinstance(batch, dict) and 'error' in batch:
            br[str(idx_global)] = {'error': batch['error']}
            return br

        root = (batch or {}).get('result') or {}
        ok_map = root.get('result') or {}
        err_map = root.get('result_error') or {}

        if isinstance(ok_map, dict):
            ok_keys = set(str(k) for k in ok_map.keys())
        else:
            ok_keys = set()

        if isinstance(err_map, dict):
            err_keys = set(str(k) for k in err_map.keys())
        else:
            err_keys = set()

        for key in key_order:
            if key in ok_keys:
                br[str(idx_global)] = {'result': ok_map[key]}
            elif key in err_keys:
                br[str(idx_global)] = {'error': err_map[key]}
                return br  # halt=1
            else:
                br[str(idx_global)] = {
                    'error': {
                        'message': 'unknown batch slot',
                        'debug': {
                            'expected_key': key,
                            'ok_keys': sorted(list(ok_keys))[:20],
                            'err_keys': sorted(list(err_keys))[:20],
                        }
                    }
                }
                return br
            idx_global += 1

    return br


def call_list_method(
        bx_token,
        method: str,
        fields: Optional[dict] = None,
        limit: Optional[int] = None,
        allowable_error: Optional[int] = None,
        timeout: Optional[int] = 120,
        force_total: Optional[int] = None,
        log_prefix: str = '',
        batch_size: int = 50,
        v: int = 2,  # для совместимости с исходным интерфейсом
) -> Union[list, dict]:
    """
    Полный списочный метод с доборкой всех страниц через REST batch,
    не требуя bx_token.batch_api_call(). Возвращает list либо dict-обёртку (см. METHOD_WRAPPERS).

    Ожидается, что:
      - bx_token.call_api_method(method, params, timeout) -> dict JSON (как в Bitrix)
      - есть функция bx_token_convert_params(params:str) -> str; если нет — используйте convert_params из вашего модуля.
    """
    assert 1 <= batch_size <= 50, 'check: 1 <= batch_size <= 50'
    if force_total:
        limit = force_total

    # Нужна функция сборки query-строки. Берём из используемого вами модуля api_call.
    # Если у токена нет такого атрибута, попробуем импортировать из bx24.bx_utils.bitrix_api_call.
    build_query = getattr(bx_token, 'convert_params', None)
    if build_query is None:
        try:
            from bx24.bx_utils.bitrix_api_call import convert_params as _convert_params
            build_query = _convert_params
        except Exception:
            raise RuntimeError('Не найдена функция convert_params. Экспортируйте convert_params в токен или модуль.')

    fields = _check_params(method, fields)

    # Оптимизация: filter.ID = [список], и это ЕДИНСТВЕННОЕ условие в fields
    if (
        isinstance(fields, dict) and
        isinstance(fields.get('filter'), dict) and
        isinstance(fields['filter'].get('ID'), list) and
        len(fields['filter']) == 1 and
        len(fields) == 1
    ):
        ids: List[Any] = fields['filter']['ID']

        def _chunks(lst, n):
            for i in range(0, len(lst), n):
                yield lst[i:i + n]

        # Собираем команды батча по batch_size ID
        methods_cmd: List[Tuple[str, dict]] = []
        for part in _chunks(ids, batch_size):
            p = {'filter': {'ID': part}}
            if fields.get('select'):
                p['select'] = fields['select']
            methods_cmd.append((method, p))

        batch_res = _do_rest_batch(bx_token, methods_cmd, timeout=timeout, chunk_size=batch_size, build_query=build_query)
        return _unwrap_batch_res(batch_res, wrapper=METHOD_WRAPPERS.get(method))

    # «странная» пагинация — подготовим первый запрос
    if method.lower() in WEIRD_PAGINATION_METHODS:
        fields = _next_params(method, fields or {}, 0)

    # Первый запрос
    first = bx_token.call_api_method(method, params=fields and fields.copy(), timeout=timeout)

    # Складываем первый результат (он может быть list или dict с wrapper-ключом)
    result = _unwrap_batch_res(BatchResultDict(), first.get('result'), wrapper=METHOD_WRAPPERS.get(method))

    # В Bitrix у списочных методов total/next обычно на верхнем уровне JSON, не внутри result.
    next_step = first.get('next')
    total_param = first.get('total') or 0
    total_needed = min(limit, total_param) if (limit is not None) else total_param

    # Если нужно добрать
    if next_step and total_needed and next_step < total_needed:
        base_fields = fields or {}
        reqs: List[Tuple[str, dict]] = []
        step = 50
        while next_step < total_needed:
            new_fields = _next_params(method, base_fields, next_step, page_size=step)
            reqs.append((method, new_fields))
            next_step += step

        batch_res = _do_rest_batch(bx_token, reqs, timeout=timeout, chunk_size=batch_size, build_query=build_query)
        result = _unwrap_batch_res(batch_res, result, wrapper=METHOD_WRAPPERS.get(method))

    # Контроль расхождения количества (если не задан limit)
    if allowable_error is not None and limit is None:
        if isinstance(result, dict):
            wrapper = METHOD_WRAPPERS.get(method)
            result_len = len(result.get(wrapper, []))
        else:
            result_len = len(result)
        diff = abs(result_len - total_param)
        if diff > allowable_error:
            raise CallListException(
                f'Количество элементов изменилось за время выполнения запроса на {diff} (допустимо {allowable_error})'
            )

    return result
