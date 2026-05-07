import sqlite3
import re
from collections import Counter
import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
import gradio as gr
import pandas as pd

# ==========================================
# 1. Бэкенд часть (FastAPI)
# ==========================================
app = FastAPI(
    title="Quotes API",
    description="API для управления цитатами (Промежуточный экзамен)"
)

class QuoteBase(BaseModel):
    text: str
    author: str
    tags: Optional[str] = None

class QuoteResponse(QuoteBase):
    id: int

class QuoteUpdate(BaseModel):
    text: Optional[str] = None
    author: Optional[str] = None
    tags: Optional[str] = None

def get_db_connection():
    conn = sqlite3.connect('quotes.db')
    conn.row_factory = sqlite3.Row
    return conn

# --- Эндпоинты API ---

@app.get("/quotes/search/", response_model=List[QuoteResponse])
def search_quotes_by_tag(tag: str = Query(..., description="Тег для поиска")):
    conn = get_db_connection()
    search_pattern = f"%{tag}%"
    quotes = conn.execute('SELECT * FROM quotes WHERE tags LIKE ?', (search_pattern,)).fetchall()
    conn.close()
    return [dict(q) for q in quotes]

@app.post("/quotes/", response_model=QuoteResponse)
def create_quote(quote: QuoteBase):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO quotes (text, author, tags) VALUES (?, ?, ?)', (quote.text, quote.author, quote.tags))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return {"id": new_id, "text": quote.text, "author": quote.author, "tags": quote.tags}

@app.get("/quotes/", response_model=List[QuoteResponse])
def read_all_quotes():
    conn = get_db_connection()
    quotes = conn.execute('SELECT * FROM quotes').fetchall()
    conn.close()
    return [dict(q) for q in quotes]

@app.get("/quotes/{quote_id}", response_model=QuoteResponse)
def read_quote(quote_id: int):
    conn = get_db_connection()
    quote = conn.execute('SELECT * FROM quotes WHERE id = ?', (quote_id,)).fetchone()
    conn.close()
    if quote is None:
        raise HTTPException(status_code=404, detail="Цитата не найдена")
    return dict(quote)

@app.put("/quotes/{quote_id}", response_model=QuoteResponse)
def update_quote(quote_id: int, quote: QuoteUpdate):
    conn = get_db_connection()
    existing_quote = conn.execute('SELECT * FROM quotes WHERE id = ?', (quote_id,)).fetchone()
    if existing_quote is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Цитата не найдена")
    
    new_text = quote.text if quote.text else existing_quote['text']
    new_author = quote.author if quote.author else existing_quote['author']
    new_tags = quote.tags if quote.tags else existing_quote['tags']
    
    conn.execute('UPDATE quotes SET text = ?, author = ?, tags = ? WHERE id = ?', (new_text, new_author, new_tags, quote_id))
    conn.commit()
    conn.close()
    return {"id": quote_id, "text": new_text, "author": new_author, "tags": new_tags}

@app.delete("/quotes/{quote_id}")
def delete_quote(quote_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM quotes WHERE id = ?', (quote_id,))
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Цитата не найдена")
    return {"message": f"Цитата {quote_id} успешно удалена"}

# ==========================================
# 2. Фронтенд и логика (Gradio)
# ==========================================

# НОВАЯ ФУНКЦИЯ: Встроенный парсер сайта
def scrape_and_save_quotes():
    target_count = 20
    base_url = "http://quotes.toscrape.com"
    page = 1
    quotes_data = []
    
    try:
        while len(quotes_data) < target_count:
            response = httpx.get(f"{base_url}/page/{page}/")
            if response.status_code != 200:
                break
            soup = BeautifulSoup(response.text, 'html.parser')
            quotes_blocks = soup.find_all('div', class_='quote')
            
            if not quotes_blocks:
                break
                
            for block in quotes_blocks:
                if len(quotes_data) >= target_count:
                    break
                text = block.find('span', class_='text').text.strip('“”')
                author = block.find('small', class_='author').text
                tags_elements = block.find_all('a', class_='tag')
                tags = ", ".join([tag.text for tag in tags_elements])
                quotes_data.append((text, author, tags))
            page += 1
            
        if quotes_data:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.executemany('INSERT INTO quotes (text, author, tags) VALUES (?, ?, ?)', quotes_data)
            conn.commit()
            conn.close()
            return f"✅ Успешно спарсено и добавлено {len(quotes_data)} цитат с сайта quotes.toscrape.com!"
        else:
            return "⚠️ Не удалось найти цитаты на сайте."
    except Exception as e:
        return f"❌ Ошибка при парсинге: {str(e)}"

def show_all_quotes_df():
    conn = get_db_connection()
    quotes = conn.execute('SELECT id, text, author, tags FROM quotes').fetchall()
    conn.close()
    return pd.DataFrame([dict(q) for q in quotes])

def search_quotes_gradio(tag):
    empty_df = pd.DataFrame(columns=["ID", "Текст", "Автор", "Теги"])
    if not tag or not tag.strip():
        return empty_df
    conn = get_db_connection()
    search_pattern = f"%{tag.strip()}%"
    quotes = conn.execute('SELECT id, text, author, tags FROM quotes WHERE tags LIKE ?', (search_pattern,)).fetchall()
    conn.close()
    if not quotes:
        return empty_df
    return pd.DataFrame([dict(q) for q in quotes])

def add_quote_gradio(text, author, tags):
    if not text or not author:
        return "⚠️ Ошибка: Поля 'Текст' и 'Автор' обязательны для заполнения!"
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO quotes (text, author, tags) VALUES (?, ?, ?)', (text, author, tags))
    conn.commit()
    conn.close()
    return f"✅ Успешно! Цитата от '{author}' добавлена в базу."

def analyze_word_frequency():
    conn = get_db_connection()
    quotes = conn.execute('SELECT text FROM quotes').fetchall()
    conn.close()
    all_text = " ".join([q['text'] for q in quotes]).lower()
    words = re.findall(r'\b[a-zа-яё]+\b', all_text)
    word_counts = Counter(words).most_common(15)
    return pd.DataFrame(word_counts, columns=['Слово', 'Частота'])

# --- Создаем интерфейс (Gradio) ---
with gr.Blocks() as gradio_app:
    gr.Markdown("# 🎓 Система управления и анализа цитат (Mid-term Project)")
    
    with gr.Tab("📚 База цитат"):
        gr.Markdown("Здесь отображаются все собранные нами цитаты из базы данных.")
        
        with gr.Row():
            load_btn = gr.Button("🔄 Загрузить / Обновить список", variant="secondary")
            # НОВАЯ КНОПКА
            scrape_btn = gr.Button("⬇️ Спарсить цитаты с quotes.toscrape.com", variant="primary")
            
        scrape_status = gr.Textbox(label="Статус парсинга", interactive=False)
        quotes_table = gr.Dataframe(headers=["ID", "Текст", "Автор", "Теги"], interactive=False)
        
        load_btn.click(fn=show_all_quotes_df, outputs=quotes_table)
        scrape_btn.click(fn=scrape_and_save_quotes, outputs=scrape_status)
        
    with gr.Tab("🔍 Поиск по тегу"):
        gr.Markdown("### Найти цитаты по ключевому слову в тегах (например: life, love, humor)")
        with gr.Row():
            search_input = gr.Textbox(label="Введите тег", placeholder="Например: life")
            search_btn = gr.Button("Найти", variant="primary")
        search_table = gr.Dataframe(headers=["ID", "Текст", "Автор", "Теги"], interactive=False)
        search_btn.click(fn=search_quotes_gradio, inputs=search_input, outputs=search_table)
        
    with gr.Tab("✍️ Добавить цитату (POST)"):
        gr.Markdown("### Добавить новую цитату вручную")
        with gr.Row():
            new_text = gr.Textbox(label="Текст цитаты")
            new_author = gr.Textbox(label="Автор")
            new_tags = gr.Textbox(label="Теги (через запятую)")
        add_btn = gr.Button("Отправить в БД", variant="primary")
        add_result = gr.Textbox(label="Статус", interactive=False)
        add_btn.click(fn=add_quote_gradio, inputs=[new_text, new_author, new_tags], outputs=add_result)

    with gr.Tab("📊 Аналитика (Word Count)"):
        gr.Markdown("### Топ-15 самых используемых слов в сохраненных цитатах")
        analyze_btn = gr.Button("Построить график частотности", variant="primary")
        stat_plot = gr.BarPlot(x="Слово", y="Частота", title="Частота слов в цитатах", tooltip=["Слово", "Частота"], color="Слово")
        analyze_btn.click(fn=analyze_word_frequency, outputs=stat_plot)

# ==========================================
# 3. МОНТИРОВАНИЕ (Mount)
# ==========================================
app = gr.mount_gradio_app(app, gradio_app, path="/gradio")