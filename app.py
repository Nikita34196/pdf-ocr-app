import streamlit as st
import pytesseract
from pdf2image import convert_from_bytes
import io
from docx import Document
import time

st.set_page_config(page_title="Независимый OCR для PDF", layout="wide")

st.title("Независимый OCR-сканер документов")
st.write("Эта версия использует классическое распознавание Tesseract. Она работает медленнее, но гарантированно обходит любые фильтры авторских прав.")

if "saved_text" not in st.session_state:
    st.session_state.saved_text = ""

st.subheader("1. Загрузка файла и выбор страниц")
uploaded_file = st.file_uploader("Выберите PDF файл", type=["pdf"])

if uploaded_file:
    # Загружаем PDF в память для подсчета страниц
    pdf_bytes = uploaded_file.read()
    
    # Конвертируем только первую страницу быстро, чтобы узнать общее количество
    # pdf2image.info возвращает информацию о файле
    try:
        from pdf2image import pdfinfo_from_bytes
        info = pdfinfo_from_bytes(pdf_bytes)
        total_pages = info["Pages"]
        st.write(f"📄 **Всего страниц в документе: {total_pages}**")
    except Exception:
        total_pages = 100 # Резервное значение, если не удалось прочитать инфо
        st.write("Не удалось точно определить количество страниц. Выберите диапазон вручную.")

    col_start, col_end = st.columns(2)
    with col_start:
        start_page = st.number_input("Начать со страницы:", min_value=1, max_value=total_pages, value=1)
    with col_end:
        end_page = st.number_input("Закончить на странице:", min_value=1, max_value=total_pages, value=10)

    st.warning("⏱️ Внимание: Классическое распознавание занимает около 5-10 секунд на каждую страницу. Рекомендуется обрабатывать не более 10-15 страниц за один раз, чтобы сервер не прервал сессию.")

    if st.button("Начать распознавание"):
        st.session_state.saved_text = ""
        progress_bar = st.progress(0)
        status = st.empty()

        try:
            # Конвертируем только выбранный диапазон страниц в изображения
            status.text(f"Подготовка страниц с {start_page} по {end_page}...")
            images = convert_from_bytes(pdf_bytes, first_page=start_page, last_page=end_page)
            
            total_images = len(images)
            
            for i, image in enumerate(images):
                current_page_num = start_page + i
                status.text(f"Распознавание страницы {current_page_num}...")
                
                # Запускаем Tesseract строго с русским языком
                text = pytesseract.image_to_string(image, lang='rus')
                
                # Очищаем лишние пустые строки для удобства чтения скринридером
                clean_text = "\n".join([line for line in text.split('\n') if line.strip()])
                
                st.session_state.saved_text += f"--- Страница {current_page_num} ---\n\n" + clean_text + "\n\n"
                
                progress_bar.progress((i + 1) / total_images)
                
            st.success("Распознавание успешно завершено!")
            
        except Exception as e:
            st.error(f"Произошла техническая ошибка: {e}")

# --- Вывод результата и скачивание ---
if st.session_state.saved_text:
    st.subheader("Результат")
    st.text_area("Распознанный текст", st.session_state.saved_text, height=400)
    
    doc = Document()
    doc.add_heading('Распознанный текст', 0)
    for paragraph in st.session_state.saved_text.split('\n'):
        if paragraph.strip():
            doc.add_paragraph(paragraph.strip())
            
    bio = io.BytesIO()
    doc.save(bio)
    
    st.download_button(
        label="Скачать документ Word (.docx)", 
        data=bio.getvalue(), 
        file_name="recognized_text_tesseract.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
