import asyncio
from parsers.avito_parser import AvitoParser

async def main():
    url = "https://www.avito.ru/moskva/kvartiry/prodam"
    parser = AvitoParser(base_url=url, max_scrolls=5)
    listings = await parser.parse()

    print(f"Спарсил {len(listings)} объявлений")
    for listing in listings[:3]:  # первые 3 для примера
        print(f"- {listing.title} | {listing.price} ₽ | {listing.location}")

if __name__ == "__main__":
    asyncio.run(main())