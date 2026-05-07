from fastapi import FastAPI
import gradio as gr
import pandas as pd
import sqlite3
from collections import Counter
from deep_translator import GoogleTranslator

# ==========================================
# 1. НАСТРОЙКА БАЗЫ ДАННЫХ
# ==========================================
def init_db():
    conn = sqlite3.connect("quotes.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT,
            author TEXT,
            tags TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 2. НАСТРОЙКА FASTAPI (Для Swagger /docs)
# ==========================================
app = FastAPI(title="Quotes API (Mid-term Project)")

@app.get("/quotes/")
def read_all_quotes():
    conn = sqlite3.connect("quotes.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM quotes")
    quotes = cursor.fetchall()
    conn.close()
    return {"quotes": quotes}

# ==========================================
# 3. ФУНКЦИИ ДЛЯ GRADIO (Логика интерфейса)
# ==========================================
def get_all_quotes_df():
    conn = sqlite3.connect("quotes.db")
    df = pd.read_sql_query("SELECT * FROM quotes", conn)
    conn.close()
    return df

def search_quotes(keyword):
    df = get_all_quotes_df()
    if keyword:
        # Ищем совпадения в колонке text (игнорируя регистр)
        filtered_df = df[df['text'].str.contains(keyword, case=False, na=False)]
        return filtered_df
    return df

def translate_text(text, target_lang):
    if not text:
        return "텍스트를 입력하세요 (Введите текст для перевода)"
    
    lang_map = {"한국어 (Korean)": "ko", "English": "en", "Русский (Russian)": "ru"}
    target = lang_map.get(target_lang, "ko")
    
    try:
        translated = GoogleTranslator(source='auto', target=target).translate(text)
        return translated
    except Exception as e:
        return f"오류 발생 (Ошибка перевода): {str(e)}"

def analyze_word_frequency():
    df = get_all_quotes_df()
    if df.empty:
        return pd.DataFrame(columns=["Word", "Count"])
    
    # Собираем все слова, переводим в нижний регистр
    all_text = " ".join(df['text'].dropna().tolist()).lower()
    # Убираем знаки препинания и берем слова длиннее 3 символов
    words = [word.strip(".,!?:;()[]\"'") for word in all_text.split() if len(word) > 3]
    
    # Считаем топ-15 слов
    word_counts = Counter(words).most_common(15)
    stat_df = pd.DataFrame(word_counts, columns=["Word", "Count"])
    return stat_df

# Функция для захвата клика по таблице
def on_table_click(evt: gr.SelectData):
    # evt.value хранит текст ячейки, по которой кликнул пользователь
    return evt.value 

# ==========================================
# 4. ИНТЕРФЕЙС GRADIO (UI)
# ==========================================
# CSS для фикса "белых квадратов" в шрифтах на Railway
custom_css = """
body, .gradio-container, .gr-button, .gr-input, .gr-markdown, table {
    font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', 'NanumGothic', sans-serif !important;
}
"""

with gr.Blocks(css=custom_css, theme=gr.themes.Soft()) as gradio_app:
    gr.Markdown("# 🎓 명언 관리 및 분석 시스템 (Quotes Management System)")
    gr.Markdown("여기에서 데이터베이스에 저장된 명언을 관리하고 분석할 수 있습니다. (Здесь вы можете управлять базой цитат и анализировать её).")

    with gr.Tabs():
        
        # --- ВКЛАДКА 1: БАЗА И ПОИСК ---
        with gr.Tab("📚 데이터베이스 및 검색 (База и поиск)"):
            with gr.Row():
                search_input = gr.Textbox(label="단어 검색 (Поиск по слову в тексте)", placeholder="검색어를 입력하세요 (Введите слово)...")
                search_btn = gr.Button("검색 (Найти)", variant="primary")
                refresh_btn = gr.Button("🔄 전체 목록 새로고침 (Обновить таблицу)")
            
            # Таблица с данными
            quotes_table = gr.Dataframe(headers=["id", "text", "author", "tags"], interactive=False)
            
            # Действия кнопок
            search_btn.click(fn=search_quotes, inputs=search_input, outputs=quotes_table)
            refresh_btn.click(fn=get_all_quotes_df, inputs=[], outputs=quotes_table)
            
            # При запуске приложения автоматически загружаем данные
            gradio_app.load(fn=get_all_quotes_df, inputs=[], outputs=quotes_table)

        # --- ВКЛАДКА 2: ПЕРЕВОДЧИК ---
        with gr.Tab("🌐 번역기 (Переводчик)"):
            gr.Markdown("### 명언 번역 (Перевод цитат)")
            gr.Markdown("*💡 팁: '데이터베이스' 탭의 표에서 셀을 클릭하면 텍스트가 자동으로 여기에 복사됩니다. (Подсказка: кликните по тексту в таблице на первой вкладке, и он автоматически появится здесь).*")
            
            with gr.Row():
                with gr.Column():
                    text_to_translate = gr.Textbox(label="원본 텍스트 (Исходный текст)", lines=4)
                    lang_choice = gr.Dropdown(
                        choices=["한국어 (Korean)", "English", "Русский (Russian)"], 
                        value="한국어 (Korean)", 
                        label="번역할 언어 (Язык перевода)"
                    )
                    translate_btn = gr.Button("번역하기 (Перевести)", variant="primary")
                with gr.Column():
                    translation_result = gr.Textbox(label="번역 결과 (Результат)", lines=4, interactive=False)
            
            translate_btn.click(
                fn=translate_text, 
                inputs=[text_to_translate, lang_choice], 
                outputs=translation_result
            )
            
            # Привязываем клик по таблице к окну перевода!
            quotes_table.select(fn=on_table_click, inputs=[], outputs=text_to_translate)

        # --- ВКЛАДКА 3: АНАЛИТИКА ---
        with gr.Tab("📊 데이터 분석 (Аналитика)"):
            gr.Markdown("### 가장 많이 사용된 단어 Top 15 (Топ-15 часто используемых слов в базе)")
            analyze_btn = gr.Button("통계 업데이트 (Построить/Обновить график)", variant="primary")
            
            stat_plot = gr.BarPlot(
                x="Word", 
                y="Count", 
                title="Word Frequency (단어 빈도수)", 
                tooltip=["Word", "Count"],
                width=600,
                height=400
            )
            
            analyze_btn.click(fn=analyze_word_frequency, inputs=[], outputs=stat_plot)


# ==========================================
# 5. МОНТИРОВАНИЕ GRADIO К FASTAPI
# ==========================================
app = gr.mount_gradio_app(app, gradio_app, path="/gradio")