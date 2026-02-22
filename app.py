import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader, PdfWriter
import tempfile
import os
import time

st.set_page_config(page_title="Безлимитный OCR для PDF", layout="wide")

# Безопасная проверка ключа
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except KeyError:
    st.error("🚨 Ошибка: API-ключ не найден в секретах Streamlit.")
    st.stop()

st.title("Безлимитный OCR для PDF документов")
st.write("Загрузите документ, выберите модель и настройте параметры.")

# --- БЛОК 1: Динамическая загрузка моделей ---
st.subheader("1. Выбор ИИ-модели")

@st.cache_data(ttl=3600)
def fetch_available_models():
    model_names = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods and 'gemini' in m.name.lower():
                model_names.append(m.name.replace('models/', ''))
        return sorted(model_names, reverse=True)
    except Exception as e:
        return ["gemini-2.5-pro", "gemini-1.5-pro", "gemini-1.5-flash"]

available_models = fetch_available_models()
selected_model_id = st.selectbox("Выберите модель:", available_models)
model = genai.GenerativeModel(selected_model_id)

# --- БЛОК 2: Настройки обработки ---
st.subheader("2. Настройки извлечения")
col1, col2 = st.columns(2)

with col1:
    preserve_grammar = st.checkbox("Сохранять авторскую орфографию", value=True)
    extract_tables = st.checkbox("Извлекать таблицы (Markdown)", value=True)
    # НОВАЯ НАСТРОЙКА: Выбор размера фрагмента
    chunk_size = st.slider("Страниц за один запрос (меньше страниц = меньше шанс блокировки за авторские права)", min_value=1, max_value=20, value=5)

with col2:
    accessibility_mode = st.checkbox("Оптимизировать структуру для чтения", value=False)
    translation = st.selectbox("Перевод текста:", ["Не переводить", "Перевести на русский", "Перевести на английский"])

# --- БЛОК 3: Загрузка файла ---
st.subheader("3. Загрузка файла")
uploaded_file = st.file_uploader("Выберите PDF файл", type=["pdf"])

if uploaded_file and st.button("Начать распознавание"):
    pdf_reader = PdfReader(uploaded_file)
    total_pages = len(pdf_reader.pages)
    full_text = ""
    
    progress_bar = st.progress(0)
    status = st.empty()

    for i in range(0, total_pages, chunk_size):
        end_page = min(i + chunk_size, total_pages)
        status.text(f"Распознавание страниц {i+1}-{end_page} из {total_pages}...")
        
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
                prompt_parts.append("Точно сохраняй исходную орфографию и пунктуацию.")
            if extract_tables:
                prompt_parts.append("Таблицы преобразуй в формат Markdown.")
            if accessibility_mode:
                prompt_parts.append("Делай четкие абзацы и убирай переносы слов внутри предложений.")
            if translation != "Не переводить":
                lang = translation.split()[-1]
                prompt_parts.append(f"Переведи текст на {lang} язык.")
            
            final_prompt = " ".join(prompt_parts)
            
            response = model.generate_content([gemini_file, final_prompt])
            
            # Добавлена обработка пустого ответа
            if not response.parts:
                raise Exception("finish_reason is 4")
                
            full_text += response.text + "\n\n---\n\n"
            genai.delete_file(gemini_file.name)
            
        except Exception as e:
            error_msg = str(e)
            # УМНАЯ ОБРАБОТКА ОШИБКИ АВТОРСКИХ ПРАВ
            if "finish_reason is 4" in error_msg or "RECITATION" in error_msg:
                st.warning(f"⚠️ Страницы {i+1}-{end_page} заблокированы антипиратским фильтром Google. Пропускаем...")
                full_text += f"\n\n[ ТЕКСТ НА СТРАНИЦАХ {i+1}-{end_page} СКРЫТ ИЗ-ЗА ЗАЩИТЫ АВТОРСКИХ ПРАВ GOOGLE ]\n\n---\n\n"
            else:
                st.error(f"Произошла ошибка на страницах {i+1}-{end_page}: {e}")
                full_text += f"\n\n[ ТЕХНИЧЕСКАЯ ОШИБКА НА СТРАНИЦАХ {i+1}-{end_page} ]\n\n---\n\n"
        finally:
            os.remove(tmp_path)
        
        progress_bar.progress(end_page / total_pages)
        time.sleep(4) 
        
    st.success("Распознавание завершено!")
    st.text_area("Итоговый результат", full_text, height=500)
    
    st.download_button(
        label="Скачать текст (.txt)", 
        data=full_text, 
        file_name=f"recognized_text_{selected_model_id}.txt",
        mime="text/plain"
    )