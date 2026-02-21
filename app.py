import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader, PdfWriter
import tempfile
import os
import time

# Ваш API ключ
genai.configure(api_key="AIzaSyCxh8H2vkk-ArHWQ3yWCDNqGNZLJ9q32YY")

# Настройка широкого формата страницы для удобства чтения
st.set_page_config(page_title="Безлимитный OCR для PDF", layout="wide")

st.title("Безлимитный OCR для PDF документов")
st.write("Загрузите документ, выберите модель и настройте параметры извлечения текста. Система автоматически обойдет лимиты объема.")

# --- БЛОК 1: Выбор модели ---
st.subheader("1. Выбор ИИ-модели")
model_options = {
    "Gemini 3.1 Pro (Новейшая, для сложного форматирования)": "gemini-3.1-pro",
    "Gemini 1.5 Pro (Мощная, высокое качество)": "gemini-1.5-pro",
    "Gemini 1.5 Flash (Быстрая, базовая)": "gemini-1.5-flash"
}

selected_model_label = st.selectbox("Доступные модели:", list(model_options.keys()))
selected_model_id = model_options[selected_model_label]
model = genai.GenerativeModel(selected_model_id)

# --- БЛОК 2: Настройки обработки текста ---
st.subheader("2. Настройки извлечения")
col1, col2 = st.columns(2)

with col1:
    preserve_grammar = st.checkbox("Строго сохранять авторскую орфографию и пунктуацию (полезно для языкового анализа)", value=True)
    extract_tables = st.checkbox("Извлекать таблицы с сохранением структуры (в формате Markdown)", value=True)

with col2:
    accessibility_mode = st.checkbox("Оптимизировать структуру для скринридеров и брайлевских дисплеев (удалить разрывы строк, выделить заголовки)", value=False)
    translation = st.selectbox("Перевод текста (опционально):", ["Не переводить", "Перевести на русский", "Перевести на английский"])

# --- БЛОК 3: Загрузка и обработка ---
st.subheader("3. Загрузка файла")
uploaded_file = st.file_uploader("Выберите PDF файл (любого объема)", type=["pdf"])

if uploaded_file and st.button("Начать распознавание"):
    pdf_reader = PdfReader(uploaded_file)
    total_pages = len(pdf_reader.pages)
    chunk_size = 15 # Обрабатываем по 15 страниц за раз
    full_text = ""
    
    progress_bar = st.progress(0)
    status = st.empty()

    for i in range(0, total_pages, chunk_size):
        end_page = min(i + chunk_size, total_pages)
        status.text(f"Распознавание страниц {i+1}-{end_page} из {total_pages} (Модель: {selected_model_id})...")
        
        writer = PdfWriter()
        for j in range(i, end_page):
            writer.add_page(pdf_reader.pages[j])
            
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            writer.write(tmp.name)
            tmp_path = tmp.name
            
        try:
            gemini_file = genai.upload_file(tmp_path)
            
            # Динамически собираем промпт на основе выбранных настроек
            prompt_parts = ["Распознай и извлеки весь текст из этого документа."]
            
            if preserve_grammar:
                prompt_parts.append("Точно сохраняй исходную орфографию, пунктуацию и грамматические конструкции текста, не исправляй опечатки автора.")
            if extract_tables:
                prompt_parts.append("Если в тексте есть таблицы, преобразуй их в текстовый формат Markdown, сохраняя столбцы и строки.")
            if accessibility_mode:
                prompt_parts.append("Структурируй текст так, чтобы он был максимально удобен для программ экранного доступа: делай четкие абзацы, убирай переносы слов внутри предложений, используй логические заголовки.")
            if translation != "Не переводить":
                lang = translation.split()[-1] # Получаем слово "русский" или "английский"
                prompt_parts.append(f"Переведи весь извлеченный текст на {lang} язык.")
            
            final_prompt = " ".join(prompt_parts)
            
            # Отправка в API
            response = model.generate_content([gemini_file, final_prompt])
            
            full_text += response.text + "\n\n---\n\n"
            
            # Очистка файла из Google AI Studio
            genai.delete_file(gemini_file.name)
            
        except Exception as e:
            st.error(f"Произошла ошибка на страницах {i+1}-{end_page}: {e}")
            if "404" in str(e) or "not found" in str(e).lower():
                st.warning("Внимание: Ваш API-ключ, возможно, еще не имеет доступа к модели 3.1. Пожалуйста, выберите Gemini 1.5 Pro или Flash.")
        finally:
            os.remove(tmp_path)
        
        progress_bar.progress(end_page / total_pages)
        # Пауза в 4 секунды между запросами для обхода лимитов
        time.sleep(4) 
        
    st.success("Распознавание всего документа успешно завершено!")
    st.text_area("Итоговый результат", full_text, height=500)
    
    # Кнопка скачивания
    st.download_button(
        label="Скачать текст (.txt)", 
        data=full_text, 
        file_name="recognized_text.txt",
        mime="text/plain"
    )