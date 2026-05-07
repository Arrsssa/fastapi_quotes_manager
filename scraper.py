import httpx
from bs4 import BeautifulSoup
import sqlite3

# 1. Настройка базы данных
def setup_database():
    # Создаем подключение к базе данных (файл quotes.db появится в папке с проектом)
    conn = sqlite3.connect('quotes.db')
    cursor = conn.cursor()
    
    # Создаем таблицу, если она еще не существует
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            author TEXT NOT NULL,
            tags TEXT
        )
    ''')
    conn.commit()
    return conn

# 2. Функция для парсинга цитат
def scrape_quotes(target_count=20):
    base_url = "http://quotes.toscrape.com"
    page = 1
    quotes_data = []
    
    print(f"Начинаем сбор {target_count} цитат...")
    
    # Цикл работает, пока мы не соберем нужное количество цитат
    while len(quotes_data) < target_count:
        # HTTPX заменяет requests, он быстрее и современнее
        response = httpx.get(f"{base_url}/page/{page}/")
        
        # Если страницы закончились (на всякий случай)
        if response.status_code != 200:
            break
            
        # Отдаем HTML-код страницы "супу" (BeautifulSoup) для поиска нужных элементов
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Находим все блоки с классом 'quote'
        quotes_blocks = soup.find_all('div', class_='quote')
        
        if not quotes_blocks:
            break # Если на странице нет цитат, выходим из цикла
            
        for block in quotes_blocks:
            if len(quotes_data) >= target_count:
                break
                
            # Достаем текст цитаты (убираем лишние кавычки по краям)
            text = block.find('span', class_='text').text.strip('“”')
            
            # Достаем автора
            author = block.find('small', class_='author').text
            
            # Достаем теги (категории) и объединяем их в одну строку через запятую
            tags_elements = block.find_all('a', class_='tag')
            tags = ", ".join([tag.text for tag in tags_elements])
            
            # Добавляем в наш список
            quotes_data.append((text, author, tags))
            
        print(f"Собрано {len(quotes_data)}/{target_count} (Страница {page})")
        page += 1 # Переходим на следующую страницу
        
    return quotes_data

# 3. Сохранение данных в БД
def save_to_db(conn, quotes):
    cursor = conn.cursor()
    # Вставляем все собранные данные в таблицу
    cursor.executemany('INSERT INTO quotes (text, author, tags) VALUES (?, ?, ?)', quotes)
    conn.commit()
    print("Успешно сохранено в базу данных SQLite3 (quotes.db)!")

# --- Основной блок запуска ---
if __name__ == "__main__":
    db_connection = setup_database()
    scraped_quotes = scrape_quotes(target_count=20)
    
    if scraped_quotes:
        save_to_db(db_connection, scraped_quotes)
        
    db_connection.close()
    print("Парсинг завершен.")