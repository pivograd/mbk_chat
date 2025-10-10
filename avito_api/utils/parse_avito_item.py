import traceback
import asyncio
import time

# from selenium import webdriver
# from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.common.by import By

from telegram.send_log import send_dev_telegram_log


def _parse_avito_ad_sync(url: str) -> dict:
    """Синхронный парсер (твой рабочий код, чуть поправленный)."""
    # data = {"title": None, "description": None}
    # driver = None
    # try:
    #     chrome_options = Options()
    #     chrome_options.add_argument("--headless=new")  # для новых Chrome
    #     chrome_options.add_argument("--no-sandbox")
    #     chrome_options.add_argument("--disable-dev-shm-usage")
    #     chrome_options.add_argument("--disable-gpu")  # безвредно в headless
    #     chrome_options.add_argument("--window-size=1920,1080")
    #     chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    #     chrome_options.add_argument(
    #         "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    #         "AppleWebKit/537.36 (KHTML, like Gecko) "
    #         "Chrome/116.0.0.0 Safari/537.36"
    #     )
    #
    #     driver = webdriver.Chrome(
    #         options=chrome_options
    #     )
    #     driver.get(url)
    #     time.sleep(3)  # пока так TODO: сделать через нормальное явное ожижание например selenium.webdriver.support.ui.WebDriverWait
    #
    #     try:
    #         data["title"] = driver.find_element(By.TAG_NAME, "h1").text.strip()
    #     except Exception:
    #         data["title"] = None
    #
    #     try:
    #         desc_el = driver.find_element(By.CSS_SELECTOR, "[data-marker='item-view/item-description']")
    #         data["description"] = desc_el.text.strip()
    #     except Exception:
    #         data["description"] = None
    #
    #     return data
    # finally:
    #     if driver:
    #         try:
    #             driver.quit()
    #         except Exception:
    #             pass
    ...


async def parse_avito_ad(url: str) -> dict:
    """Асинхронная обёртка."""
    # try:
    #     return await asyncio.to_thread(_parse_avito_ad_sync, url)
    # except Exception:
    #     tb = traceback.format_exc()
    #     await send_dev_telegram_log(
    #         f'Ошибка при парсинге объявления с Авито:\nurl: {url}\nTRACEBACK:\n{tb}'
    #     )
    #     return {"title": None, "description": None}
    ...
