import os
import asyncio
import json
import logging
from datetime import datetime
from playwright.async_api import async_playwright
from aiohttp import web

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class YandexTravelParser:
    def __init__(self):
        self.reviews_dir = "reviews"
        os.makedirs(self.reviews_dir, exist_ok=True)
    
    async def scrape_reviews(self):
        """Основная функция парсинга отзывов"""
        logger.info("Запуск парсинга отзывов...")
        
        # На Render используем headless=True
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = await context.new_page()

            try:
                # Переходим на страницу отеля
                await page.goto(
                    'https://travel.yandex.ru/hotels/nizhny-novgorod-oblast/seraphim-grad/?adults=2&checkinDate=2025-10-03&checkoutDate=2025-10-06&childrenAges=&searchPagePollingId=70a7e05752d9c15a97f175e268c7e69f-0-newsearch&seed=portal-hotels-search',
                    wait_until='domcontentloaded',
                    timeout=60000
                )

                await page.wait_for_timeout(3000)

                # Кликнуть на "Отзывы"
                await page.wait_for_selector('button:has-text("Отзывы")', timeout=10000)
                await page.click('button:has-text("Отзывы")')
                await page.wait_for_timeout(2000)

                # Скролл + клик по "Еще отзывы"
                last_height = await page.evaluate('document.body.scrollHeight')
                scroll_attempts = 0
                max_scroll_attempts = 10  # Ограничим количество прокруток

                while scroll_attempts < max_scroll_attempts:
                    await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    await page.wait_for_timeout(1000)

                    show_more_button = await page.query_selector('button:has-text("Еще отзывы")')
                    if show_more_button:
                        logger.info('Найдена кнопка "Еще отзывы" — кликаем...')
                        await show_more_button.click()
                        await page.wait_for_timeout(2000)

                    new_height = await page.evaluate('document.body.scrollHeight')
                    if new_height == last_height:
                        break
                    last_height = new_height
                    scroll_attempts += 1

                # Получаем общее количество отзывов
                total_reviews = await page.locator('section.root.mQbD7.esfDh.xa7LR').count()
                logger.info(f'Общее количество отзывов: {total_reviews}')

                # Извлекаем данные отзывов
                reviews = await page.evaluate("""() => {
                    const items = document.querySelectorAll('section.root.mQbD7.esfDh.xa7LR');
                    return Array.from(items).map(el => {
                        const avatarEl = el.querySelector('img.u91mj');
                        const nameEl = el.querySelector('span._3iE2j.BUTjn.b9-76');
                        const dateEl = el.querySelector('span.Eqn7e.dNANh');

                        // Извлечение текста отзыва
                        let text = '';
                        const textContainer = el.querySelector('div.lpglK.Eqn7e.b9-76 > div[style*="word-wrap"]');
                        if (textContainer) {
                            text = textContainer.textContent.trim();
                        }

                        // Извлечение оценки по aria-selected
                        let rating = 0;
                        const ratingContainer = el.querySelector('div.Ia-4D.vdDWU.KNw-o.tzdr8');
                        if (ratingContainer) {
                            const stars = ratingContainer.querySelectorAll('[aria-selected="true"]');
                            rating = stars.length;
                        }

                        const name = nameEl?.textContent?.trim() || 'Аноним';
                        const date = dateEl?.textContent?.trim() || '';
                        const avatarSrc = avatarEl?.src || null;

                        return { rating, text, name, date, avatarSrc };
                    });
                }""")

                logger.info(f'Все оценки: {[r["rating"] for r in reviews]}')

                # Фильтруем отзывы с оценкой >= 3
                filtered_reviews = [r for r in reviews if r['rating'] >= 3]
                count3 = len([r for r in filtered_reviews if r['rating'] == 3])
                count4 = len([r for r in filtered_reviews if r['rating'] == 4])
                count5 = len([r for r in filtered_reviews if r['rating'] == 5])

                logger.info(f'Отзывов с оценкой 3: {count3}')
                logger.info(f'Отзывов с оценкой 4: {count4}')
                logger.info(f'Отзывов с оценкой 5: {count5}')
                logger.info(f'Всего отфильтрованных отзывов: {len(filtered_reviews)}')

                # Сохраняем результаты
                output_path = os.path.join(self.reviews_dir, 'reviews.json')
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(filtered_reviews, f, ensure_ascii=False, indent=2)
                
                logger.info(f'Результаты сохранены в {output_path}')
                return {
                    'status': 'success',
                    'total_reviews': total_reviews,
                    'filtered_reviews': len(filtered_reviews),
                    'count_3': count3,
                    'count_4': count4,
                    'count_5': count5,
                    'last_updated': datetime.now().isoformat()
                }

            except Exception as e:
                logger.error(f'Ошибка при парсинге: {e}')
                return {'status': 'error', 'message': str(e)}
            finally:
                await browser.close()

# Создаем экземпляр парсера
parser = YandexTravelParser()

# Веб-сервер для Render
async def handle_scrape(request):
    """Обработчик для запуска парсинга"""
    try:
        result = await parser.scrape_reviews()
        return web.json_response(result)
    except Exception as e:
        return web.json_response({'status': 'error', 'message': str(e)})

async def handle_status(request):
    """Статус приложения"""
    return web.json_response({
        'status': 'running',
        'service': 'Yandex Travel Parser',
        'timestamp': datetime.now().isoformat()
    })

async def handle_reviews(request):
    """Получить последние результаты"""
    try:
        with open('reviews/reviews.json', 'r', encoding='utf-8') as f:
            reviews = json.load(f)
        return web.json_response({
            'status': 'success',
            'count': len(reviews),
            'reviews': reviews[:10]  # Первые 10 отзывов
        })
    except FileNotFoundError:
        return web.json_response({
            'status': 'error', 
            'message': 'Данные еще не собраны'
        })

async def init_app():
    """Инициализация приложения"""
    app = web.Application()
    app.router.add_get('/', handle_status)
    app.router.add_get('/scrape', handle_scrape)
    app.router.add_get('/reviews', handle_reviews)
    return app

if __name__ == '__main__':
    # Установка Playwright браузеров при первом запуске
    async def setup():
        import subprocess
        logger.info("Установка браузеров Playwright...")
        subprocess.run(['playwright', 'install', 'chromium'], check=True)
        
        # Запуск веб-сервера
        app = await init_app()
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get('PORT', 5000)))
        await site.start()
        logger.info("Сервер запущен на порту 5000")
        
        # Бесконечный цикл для поддержания работы
        await asyncio.Event().wait()
    
    asyncio.run(setup())
    