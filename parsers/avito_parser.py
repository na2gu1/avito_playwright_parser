import asyncio
import re
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from models.listing import AvitoListing

class AvitoParser:
    def __init__(self, base_url: str, max_scrolls: int = 10):
        self.base_url = base_url
        self.max_scrolls = max_scrolls

    async def parse(self) -> list[AvitoListing]:
        async with async_playwright() as p:
            # Запускаем браузер с настройками для обхода детекта
            browser = await p.chromium.launch(
                headless=True,
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
                await page.wait_for_selector("div[data-marker='item']", timeout=10000)
            except PlaywrightTimeout:
                print("Не удалось загрузить объявления. Возможно, защита Авито.")
                await browser.close()
                return []

            # Извлекаем все карточки
            items = await page.query_selector_all("div[data-marker='item']")

            listings = []
            for item in items:
                try:
                    # URL и ID
                    link_el = await item.query_selector("a[data-marker='item-title']")
                    if not link_el:
                        continue
                    url = await link_el.get_attribute("href")
                    if not url or "avito.ru" not in url:
                        continue
                    if url.startswith("/"):
                        url = "https://www.avito.ru" + url

                    # Извлекаем ID из URL
                    avito_id_match = re.search(r"_(\d+)$", url)
                    avito_id = avito_id_match.group(1) if avito_id_match else "unknown"

                    # Заголовок
                    title = await (await link_el.text_content()).strip()

                    # Цена
                    price_el = await item.query_selector("span[itemprop='price']")
                    price_text = await price_el.text_content() if price_el else ""
                    price = None
                    if price_text:
                        # Убираем всё кроме цифр
                        price_digits = re.sub(r"[^\d]", "", price_text)
                        if price_digits:
                            price = int(price_digits)

                    # Локация
                    location_el = await item.query_selector("div[data-marker='item-address'] > span")
                    location = await location_el.text_content() if location_el else None

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