import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader, PdfWriter
import tempfile
import os
import time

# Безопасное подключение ключа из секретов Streamlit
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

st.set_page_config(page_title="Безлимитный OCR для PDF", layout="wide")

st.title("Безлимитный OCR для PDF документов")
st.write("Загрузите документ, выберите модель и настройте параметры. Система автоматически обойдет лимиты объема.")

# --- БЛОК 1: Динамическая загрузка всех доступных моделей ---
st.subheader("1. Выбор ИИ-модели")

@st.cache_data(ttl=3600)
def fetch_available_models():
    model_names = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods and 'gemini' in m.name.lower():
                clean_name = m.name.replace('models/', '')
                model_names.append(clean_name)
        return sorted(model_names, reverse=True)
    except Exception as e:
        st.error(f"Не удалось загрузить список моделей: {e}")
        return ["gemini-2.5-pro", "gemini-1.5-pro", "gemini-1.5-flash"]

available_models = fetch_available_models()
selected_model_id = st.selectbox("Выберите модель:", available_models)
model = genai.GenerativeModel(selected_model_id)

# --- БЛОК 2: Настройки обработки текста ---
st.subheader("2. Настройки извлечения")
col1, col2 = st.columns(2)

with col1:
    preserve_grammar = st.checkbox("Строго сохранять авторскую орфографию и пунктуацию", value=True)
    extract_tables = st.checkbox("Извлекать таблицы с сохранением структуры (Markdown)", value=True)

with col2:
    accessibility_mode = st.checkbox("Оптимизировать структуру (убрать разрывы строк, выделить заголовки)", value=False)
    translation = st.selectbox("Перевод текста (опционально):", ["Не переводить", "Перевести на русский", "Перевести на английский"])

# --- БЛОК 3: Загрузка и обработка ---
st.subheader("3. Загрузка файла")
uploaded_file = st.file_uploader("Выберите PDF файл (любого объема)", type=["pdf"])

if uploaded_file and st.button("Начать распознавание"):
    pdf_reader = PdfReader(uploaded_file)
    total_pages = len(pdf_reader.pages)
    chunk_size = 15 
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
            
            prompt_parts = ["Распознай и извлеки весь текст из этого документа."]
            if preserve_grammar:
                prompt_parts.append("Точно сохраняй исходную орфографию, пунктуацию и грамматические конструкции текста, не исправляй опечатки автора.")
            if extract_tables:
                prompt_parts.append("Если в тексте есть таблицы, преобразуй их в текстовый формат Markdown.")
            if accessibility_mode:
                prompt_parts.append("Структурируй текст так, чтобы он был максимально удобен для чтения: делай четкие абзацы, убирай переносы слов внутри предложений, используй логические заголовки.")
            if translation != "Не переводить":
                lang = translation.split()[-1]
                prompt_parts.append(f"Переведи весь извлеченный текст на {lang} язык.")
            
            final_prompt = " ".join(prompt_parts)
            
            response = model.generate_content([gemini_file, final_prompt])
            full_text += response.text + "\n\n---\n\n"
            genai.delete_file(gemini_file.name)
            
        except Exception as e:
            st.error(f"Произошла ошибка на страницах {i+1}-{end_page}. Сервер ответил: {e}")
        finally:
            os.remove(tmp_path)
        
        progress_bar.progress(end_page / total_pages)
        time.sleep(4) 
        
    st.success("Распознавание всего документа успешно завершено!")
    st.text_area("Итоговый результат", full_text, height=500)
    
    st.download_button(
        label="Скачать текст (.txt)", 
        data=full_text, 
        file_name=f"recognized_text_{selected_model_id}.txt",
        mime="text/plain"
    )