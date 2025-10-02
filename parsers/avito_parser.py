import asyncio
import re
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from models.listing import AvitoListing
from utils.logger import setup_logger

class AvitoParser:
    def __init__(self, base_url: str, max_scrolls: int = 10,):
        self.base_url = base_url
        self.max_scrolls = max_scrolls
        self.logger = setup_logger(__class__.__name__)

    async def parse(self) -> list[AvitoListing]:
        async with async_playwright() as p:
            # Запускаем браузер с настройками для обхода детекта
            browser = await p.chromium.launch(
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ]
            )

            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
            )

            page = await context.new_page()
            await page.goto(self.base_url, timeout=60000)

            # Пытаемся закрыть баннеры (если есть)
            try:
                await page.click("button[data-marker='popup-cookie-banner/accept']", timeout=3000)
            except PlaywrightTimeout:
                pass

            # Скроллим вниз, чтобы подгрузить объявления
            for i in range(self.max_scrolls):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)  # дать время подгрузиться

            # Ждём появления хотя бы одного объявления
            try:
                await page.wait_for_selector("div[id^='i']", timeout=15000)
            except PlaywrightTimeout:
                self.logger.error("Не найдено ни одного объявления по ID-паттерну")
                await browser.close()
                return []

            # Получаем все объявления по ID
            items = await page.query_selector_all("div[id^='i']")
            self.logger.info(f"Найдено {len(items)} объявлений по ID-паттерну")

            listings = []
            for item in items:
                try:
                    # URL и ID
                    link_el = await item.query_selector("a[href*='/moskva/']")
                    if not link_el:
                     link_el = await item.query_selector("a")  # fallback

                    if not link_el:
                        self.logger.warning(f"Не найдена ссылка в объявлении (элемент без <a>)")
                        continue

                    url = await link_el.get_attribute("href")
                    if not url or not isinstance(url, str):
                        self.logger.warning(f"Некорректный href в объявлении")
                        continue

                    if url.startswith("/"):
                        url = "https://www.avito.ru" + url
                    elif not url.startswith("http"):
                        self.logger.warning(f"Неожиданный формат URL: {url}")
                        continue

                    # Извлекаем ID из URL
                    avito_id_match = re.search(r"_(\d+)$", url)
                    avito_id = avito_id_match.group(1) if avito_id_match else "unknown"

                    # Заголовок
                    title = (await link_el.text_content()).strip()

                    # Цена
                    price_el = await item.query_selector("span[itemprop='price']")
                    if price_el:
                        price_text = await price_el.text_content()
                    else:
                        price_text = ""

                    price = None
                    if price_text:
                        price_digits = re.sub(r"[^\d]", "", price_text)
                        if price_digits:
                            price = int(price_digits)

                    # Локация
                    location_el = await item.query_selector("div[data-marker='item-address'] > span")
                    location = (await location_el.text_content()) if location_el else None

                    # Тип продавца
                    seller_badge = await item.query_selector("div[data-marker='item-specific-params'] span")
                    seller_type = None
                    if seller_badge:
                        badge_text = await seller_badge.text_content()
                        if "частное" in badge_text.lower():
                            seller_type = "Частное лицо"
                        elif "компан" in badge_text.lower() or "агент" in badge_text.lower():
                            seller_type = "Компания"

                    # Изображения (первое изображение из data-srcset)
                    img_el = await item.query_selector("img[itemprop='image']")
                    image_urls = []
                    if img_el:
                        srcset = await img_el.get_attribute("srcset")
                        if srcset:
                            # Берём первый URL из srcset
                            first_url = srcset.split(",")[0].split(" ")[0]
                            if first_url.startswith("//"):
                                first_url = "https:" + first_url
                            image_urls = [first_url]

                    listing = AvitoListing(
                        avito_id=avito_id,
                        title=title,
                        price=price,
                        url=url,
                        location=location,
                        seller_type=seller_type,
                        image_urls=image_urls,
                        parsed_at=datetime.utcnow()
                    )
                    listings.append(listing)

                except Exception as e:
                    print(f"Ошибка при парсинге карточки: {e}")
                    continue

            await browser.close()
            return listings