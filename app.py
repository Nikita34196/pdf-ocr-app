import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader, PdfWriter
import tempfile
import os
import time

# Ваш API ключ встроен напрямую
genai.configure(api_key="AIzaSyCxh8H2vkk-ArHWQ3yWCDNqGNZLJ9q32YY")
model = genai.GenerativeModel('gemini-1.5-flash')

st.title("Безлимитный OCR для PDF")
st.write("Загрузите документ, и система распознает его целиком, обходя лимиты.")

uploaded_file = st.file_uploader("Выберите PDF файл", type=["pdf"])

if uploaded_file and st.button("Начать распознавание"):
    # Читаем загруженный PDF
    pdf_reader = PdfReader(uploaded_file)
    total_pages = len(pdf_reader.pages)
    chunk_size = 15 # Разбиваем по 15 страниц
    full_text = ""
    
    progress_bar = st.progress(0)
    status = st.empty()

    for i in range(0, total_pages, chunk_size):
        end_page = min(i + chunk_size, total_pages)
        status.text(f"Распознавание страниц {i+1}-{end_page} из {total_pages}...")
        
        # Создаем временный PDF только для текущих 15 страниц
        writer = PdfWriter()
        for j in range(i, end_page):
            writer.add_page(pdf_reader.pages[j])
            
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            writer.write(tmp.name)
            tmp_path = tmp.name
            
        try:
            # Отправляем фрагмент в Google Gemini
            gemini_file = genai.upload_file(tmp_path)
            prompt = "Распознай и извлеки весь текст из этого документа. Сохраняй абзацы и структуру."
            response = model.generate_content([gemini_file, prompt])
            
            full_text += response.text + "\n\n"
            
            # Удаляем временные файлы с серверов Google и локального
            genai.delete_file(gemini_file.name)
        except Exception as e:
            st.error(f"Произошла ошибка на страницах {i+1}-{end_page}: {e}")
        finally:
            os.remove(tmp_path)
        
        # Обновляем прогресс-бар и делаем паузу, чтобы не превысить частоту запросов API
        progress_bar.progress(end_page / total_pages)
        time.sleep(3) 
        
    st.success("Распознавание завершено!")
    st.text_area("Результат", full_text, height=400)
    st.download_button("Скачать текст (.txt)", full_text, file_name="recognized_text.txt")