import streamlit as st
from pdf2image import convert_from_bytes

st.title("Test OCR con pdf2image y Poppler")

uploaded_file = st.file_uploader("Sube un PDF escaneado", type=["pdf"])

if uploaded_file is not None:
    pdf_bytes = uploaded_file.read()

    poppler_path = r"C:\Users\Maria\Documents\poppler-24.08.0\Library\bin"

    try:
        images = convert_from_bytes(pdf_bytes, poppler_path=poppler_path)
        st.success(f"Se generaron {len(images)} imágenes del PDF")
        for i, img in enumerate(images):
            st.image(img, caption=f"Página {i+1}")
    except Exception as e:
        st.error(f"Error al convertir PDF a imágenes: {e}")
