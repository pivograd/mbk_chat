import requests


async def get_instance_settings(wa_config):
    """Получает настройки инстанса GreenApi"""
    base_url, instance_id, api_token = wa_config.get_green_api_params()
    url = f"{base_url}/waInstance{instance_id}/getSettings/{api_token}"
    headers = {"Content-Type": "application/json"}
    response = requests.request("GET", url, headers=headers)
    return response.json()

async def get_instance_phone(wa_config):
    data = await get_instance_settings(wa_config)
    phone = data.get('wid', '').split('@')[0]
    return phone