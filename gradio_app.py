"""
gradio_app.py — Gradio UI, примонтированный к FastAPI
Запуск: uvicorn gradio_app:app --reload
Docs API:  http://127.0.0.1:8000/docs
Gradio UI: http://127.0.0.1:8000/ui
"""

import gradio as gr
import httpx
from collections import Counter
import re

# ─── Настройки ───────────────────────────────────────────────────────────────

API_BASE = "http://127.0.0.1:8000"   # адрес FastAPI (сам себя)

# Стоп-слова — не считаем их при анализе частот
STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "is", "it", "that", "this", "you", "i", "we", "he",
    "she", "they", "not", "be", "as", "are", "was", "have", "has", "do",
    "by", "from", "your", "our", "their", "my", "so", "if", "what",
    "which", "who", "when", "there", "than", "more", "no", "can", "will",
}

# ─── Вспомогательные функции ─────────────────────────────────────────────────

def api_get(path: str, params: dict = None):
    try:
        r = httpx.get(f"{API_BASE}{path}", params=params, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def api_post(path: str, data: dict):
    try:
        r = httpx.post(f"{API_BASE}{path}", json=data, timeout=5)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        return {"error": e.response.json().get("detail", str(e))}
    except Exception as e:
        return {"error": str(e)}


def api_patch(path: str, data: dict):
    try:
        r = httpx.patch(f"{API_BASE}{path}", json=data, timeout=5)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        return {"error": e.response.json().get("detail", str(e))}
    except Exception as e:
        return {"error": str(e)}


def api_delete(path: str):
    try:
        r = httpx.delete(f"{API_BASE}{path}", timeout=5)
        if r.status_code == 204:
            return {"ok": True}
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        return {"error": e.response.json().get("detail", str(e))}
    except Exception as e:
        return {"error": str(e)}


def word_frequency(texts: list[str], top_n: int = 15) -> tuple[list[str], list[int]]:
    """Подсчитывает частоту слов из списка текстов."""
    words = []
    for text in texts:
        tokens = re.findall(r"[a-zA-Z']+", text.lower())
        words.extend(w for w in tokens if w not in STOPWORDS and len(w) > 2)
    counter = Counter(words).most_common(top_n)
    if not counter:
        return [], []
    labels, values = zip(*counter)
    return list(labels), list(values)


def format_quotes_table(items: list[dict]) -> list[list]:
    """Форматирует список афоризмов для gr.Dataframe."""
    return [
        [q["id"], q["author"], q["tags"], q["text"][:80] + ("…" if len(q["text"]) > 80 else "")]
        for q in items
    ]


# ─── Функции вкладок ─────────────────────────────────────────────────────────

# ── Вкладка 1: Просмотр и поиск ──────────────────────────────────────────────

def tab_browse(search_query: str, author_filter: str, tag_filter: str, page: int):
    if search_query.strip():
        data = api_get("/quotes/search/", {"q": search_query})
        if isinstance(data, list):
            items = data
            total = len(items)
            info = f"🔍 Найдено: {total}"
        else:
            return [], f"❌ Ошибка: {data.get('error')}"
    else:
        params = {"page": page, "size": 10}
        if author_filter.strip():
            params["author"] = author_filter
        if tag_filter.strip():
            params["tag"] = tag_filter
        data = api_get("/quotes", params)
        if "error" in data:
            return [], f"❌ Ошибка: {data['error']}"
        items = data["items"]
        total = data["total"]
        info = f"📚 Всего афоризмов: {total} | Страница {page}"

    table = format_quotes_table(items)
    return table, info


# ── Вкладка 2: Добавить афоризм ───────────────────────────────────────────────

def tab_create(text: str, author: str, tags: str):
    if not text.strip() or not author.strip():
        return "⚠️ Заполните текст и автора."
    result = api_post("/quotes", {"text": text.strip(), "author": author.strip(), "tags": tags.strip()})
    if "error" in result:
        return f"❌ Ошибка: {result['error']}"
    return f"✅ Добавлен афоризм #{result['id']} — {result['author']}"


# ── Вкладка 3: Редактировать ──────────────────────────────────────────────────

def tab_update(quote_id: int, new_text: str, new_author: str, new_tags: str):
    payload = {}
    if new_text.strip():   payload["text"]   = new_text.strip()
    if new_author.strip(): payload["author"] = new_author.strip()
    if new_tags.strip():   payload["tags"]   = new_tags.strip()
    if not payload:
        return "⚠️ Введите хотя бы одно поле для обновления."
    result = api_patch(f"/quotes/{int(quote_id)}", payload)
    if "error" in result:
        return f"❌ Ошибка: {result['error']}"
    return f"✅ Обновлено: #{result['id']} — {result['author']}"


# ── Вкладка 4: Удалить ────────────────────────────────────────────────────────

def tab_delete(quote_id: int):
    result = api_delete(f"/quotes/{int(quote_id)}")
    if "error" in result:
        return f"❌ Ошибка: {result['error']}"
    return f"🗑️ Афоризм #{int(quote_id)} удалён."


# ── Вкладка 5: Аналитика ──────────────────────────────────────────────────────

def tab_analytics():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    stats = api_get("/stats")
    if "error" in stats:
        return None, None, None, f"❌ Ошибка: {stats['error']}"

    all_quotes = api_get("/quotes", {"size": 200})
    texts = [q["text"] for q in all_quotes.get("items", [])]

    # ── График 1: частота слов ────────────────────────────────────────────────
    labels, values = word_frequency(texts)
    fig1, ax1 = plt.subplots(figsize=(10, 5))
    colors = plt.cm.Blues(np.linspace(0.4, 0.9, len(labels)))
    bars = ax1.barh(labels[::-1], values[::-1], color=colors[::-1])
    ax1.set_title("Топ слов в афоризмах", fontsize=14, fontweight="bold")
    ax1.set_xlabel("Частота")
    for bar, val in zip(bars, values[::-1]):
        ax1.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                 str(val), va="center", fontsize=9)
    plt.tight_layout()

    # ── График 2: топ авторов ─────────────────────────────────────────────────
    authors = [a["author"] for a in stats["top_authors"]]
    counts  = [a["count"]  for a in stats["top_authors"]]
    fig2, ax2 = plt.subplots(figsize=(7, 5))
    wedge_colors = ["#2196F3", "#42A5F5", "#64B5F6", "#90CAF9", "#BBDEFB"]
    ax2.pie(counts, labels=authors, autopct="%1.0f%%",
            colors=wedge_colors[:len(authors)], startangle=140,
            wedgeprops={"edgecolor": "white", "linewidth": 2})
    ax2.set_title("Распределение по авторам", fontsize=14, fontweight="bold")
    plt.tight_layout()

    # ── График 3: длина афоризмов ─────────────────────────────────────────────
    lengths = [len(t.split()) for t in texts]
    fig3, ax3 = plt.subplots(figsize=(8, 4))
    ax3.hist(lengths, bins=10, color="#42A5F5", edgecolor="white", linewidth=1.2)
    ax3.set_title("Распределение длины афоризмов (в словах)", fontsize=14, fontweight="bold")
    ax3.set_xlabel("Количество слов")
    ax3.set_ylabel("Кол-во афоризмов")
    avg = sum(lengths) / len(lengths) if lengths else 0
    ax3.axvline(avg, color="#E53935", linestyle="--", label=f"Среднее: {avg:.1f} слов")
    ax3.legend()
    plt.tight_layout()

    summary = (
        f"📊 **Всего афоризмов:** {stats['total_quotes']}\n"
        f"👤 **Уникальных авторов:** {len(stats['top_authors'])}\n"
        f"🏷️ **Уникальных тегов:** {len(stats['top_tags'])}\n"
        f"📝 **Средняя длина:** {avg:.1f} слов\n\n"
        f"**Топ тегов:** " + ", ".join(f"{t['tag']} ({t['count']})" for t in stats["top_tags"][:5])
    )
    return fig1, fig2, fig3, summary


# ─── Gradio UI ───────────────────────────────────────────────────────────────

with gr.Blocks(title="Quotes Manager") as gradio_ui:

    gr.Markdown("# 📖 Quotes Manager\nСистема управления афоризмами | FastAPI + SQLite + Gradio")

    # ════════════════════════════════════════════════════════════
    with gr.Tab("📚 Просмотр и поиск"):
        with gr.Row():
            search_in  = gr.Textbox(label="🔍 Поиск по тексту/автору", placeholder="введите слово...")
            author_in  = gr.Textbox(label="👤 Фильтр по автору")
            tag_in     = gr.Textbox(label="🏷️ Фильтр по тегу")
            page_in    = gr.Number(label="Страница", value=1, minimum=1, precision=0)

        browse_btn  = gr.Button("Показать", variant="primary")
        browse_info = gr.Markdown()
        browse_table = gr.Dataframe(
            headers=["ID", "Автор", "Теги", "Текст (превью)"],
            datatype=["number", "str", "str", "str"],
            interactive=False,
        )
        browse_btn.click(
            tab_browse,
            inputs=[search_in, author_in, tag_in, page_in],
            outputs=[browse_table, browse_info],
        )

    # ════════════════════════════════════════════════════════════
    with gr.Tab("➕ Добавить"):
        add_text   = gr.Textbox(label="Текст афоризма", lines=3)
        add_author = gr.Textbox(label="Автор")
        add_tags   = gr.Textbox(label="Теги (через запятую)", placeholder="life,wisdom,inspiration")
        add_btn    = gr.Button("Добавить", variant="primary")
        add_result = gr.Markdown()
        add_btn.click(tab_create, inputs=[add_text, add_author, add_tags], outputs=add_result)

    # ════════════════════════════════════════════════════════════
    with gr.Tab("✏️ Редактировать"):
        gr.Markdown("Заполните только те поля, которые хотите изменить.")
        edit_id     = gr.Number(label="ID афоризма", precision=0)
        edit_text   = gr.Textbox(label="Новый текст", lines=2)
        edit_author = gr.Textbox(label="Новый автор")
        edit_tags   = gr.Textbox(label="Новые теги")
        edit_btn    = gr.Button("Обновить", variant="primary")
        edit_result = gr.Markdown()
        edit_btn.click(tab_update, inputs=[edit_id, edit_text, edit_author, edit_tags], outputs=edit_result)

    # ════════════════════════════════════════════════════════════
    with gr.Tab("🗑️ Удалить"):
        del_id     = gr.Number(label="ID афоризма для удаления", precision=0)
        del_btn    = gr.Button("Удалить", variant="stop")
        del_result = gr.Markdown()
        del_btn.click(tab_delete, inputs=[del_id], outputs=del_result)

    # ════════════════════════════════════════════════════════════
    with gr.Tab("📊 Аналитика"):
        analytics_btn = gr.Button("Построить графики", variant="primary")
        analytics_summary = gr.Markdown()
        with gr.Row():
            plot_words   = gr.Plot(label="Частота слов")
            plot_authors = gr.Plot(label="Топ авторов")
        plot_lengths = gr.Plot(label="Длина афоризмов")
        analytics_btn.click(
            tab_analytics,
            outputs=[plot_words, plot_authors, plot_lengths, analytics_summary],
        )


# ─── Монтируем Gradio в FastAPI ──────────────────────────────────────────────

from main import app   # импортируем FastAPI приложение из main.py

app = gr.mount_gradio_app(app, gradio_ui, path="/ui")

# ─── Точка входа ─────────────────────────────────────────────────────────────
# Запуск: uvicorn gradio_app:app --reload
# API:    http://127.0.0.1:8000/docs
# UI:     http://127.0.0.1:8000/ui
