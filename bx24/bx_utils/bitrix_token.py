from typing import Optional, Iterable, Any

from bx24.bx_utils.bitrix_api_call_v2 import api_call
from bx24.bx_utils.bitrix_call_list import call_list_method
from bx24.bx_utils.exceptions import BitrixApiError, ExpiredToken


class BaseBitrixToken:
    DEFAULT_TIMEOUT = 120

    domain = NotImplemented
    auth_token = NotImplemented
    web_hook_auth = NotImplemented

    def get_auth(self):
        return (self.web_hook_auth or self.auth_token), bool(self.web_hook_auth)

    def call_api_method(self, api_method, params=None, timeout=DEFAULT_TIMEOUT):
        auth, webhook = self.get_auth()
        try:
            response = api_call(
                domain=self.domain,
                api_method=api_method,
                auth_token=auth,
                webhook=webhook,
                params=params,
                timeout=timeout,
            )
        except Exception as e:
            raise e

        try:
            json_response = response.json()
        except ValueError:
            raise BitrixApiError(601, {"error": "json ValueError"})

        if response.status_code in (200, 201) and not json_response.get('error'):
            return json_response

        if response.status_code == 401 and json_response.get('error') == 'expired_token':
            raise ExpiredToken()

        raise BitrixApiError(response.status_code, json_response)

    call_api_method_v2 = call_api_method

    def batch_api_call(self, methods, timeout=DEFAULT_TIMEOUT, chunk_size=50, halt=0, log_prefix=''):
        """:rtype: bitrix_utils.bitrix_auth.functions.batch_api_call3.BatchResultDict
        """
        ...

    batch_api_call_v3 = batch_api_call

    def call_list_fast(
            self,
            method,  # type: str
            params=None,  # type: Optional[dict]
            descending=False,  # type: bool
            timeout=DEFAULT_TIMEOUT,  # type: Optional[int]
            log_prefix='',  # type: str
            limit=None,  # type: Optional[int]
            batch_size=50,  # type: int
    ):
        # type: (...) -> Iterable[Any]
        """Списочный запрос с параметром ?start=-1
        см. описание bitrix_utils.bitrix_auth.functions.call_list_fast.call_list_fast

        Если происходит KeyError, надо добавить описание метода
        в справочники METHOD_TO_* в bitrix_utils.bitrix_auth.functions.call_list_fast
        """
        ...

    def call_list_method(
            self,
            method: str,
            fields: Optional[dict] = None,
            limit: Optional[int] = None,
            allowable_error: Optional[int] = None,
            timeout: int = DEFAULT_TIMEOUT,
            force_total: Optional[int] = None,
            log_prefix: str = '',
            batch_size: int = 50,
    ):
        return call_list_method(
            self,
            method,
            fields=fields,
            limit=limit,
            allowable_error=allowable_error,
            timeout=timeout,
            force_total=force_total,
            log_prefix=log_prefix,
            batch_size=batch_size,
            v=2,
        )


class BitrixToken(BaseBitrixToken):
    def __init__(self, domain, auth_token=None, web_hook_auth=None):
        self.domain = domain
        self.auth_token = auth_token
        self.web_hook_auth = web_hook_auth


# встройка resp = but.call_api_method('placement.bind', {'PLACEMENT': 'CRM_DEAL_DETAIL_TAB', 'HANDLER': handler, 'TITLE': 'DEV WA CHAT'})
# handler = 'https://589f096a-5923-4449-97c8-71fcc2235775.tunnel4.com/vz/chat'