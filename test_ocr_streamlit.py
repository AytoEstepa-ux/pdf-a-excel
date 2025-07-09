import streamlit as st
import os
from pdf2image import convert_from_bytes

# Añadir poppler al PATH dentro del script
os.environ["PATH"] += os.pathsep + r"C:\Users\Maria\Documents\poppler-24.08.0\Library\bin"

st.title("Test OCR con pdf2image y Poppler")

uploaded_file = st.file_uploader("Sube un PDF escaneado", type=["pdf"])

if uploaded_file is not None:
    pdf_bytes = uploaded_file.read()

    try:
        images = convert_from_bytes(pdf_bytes)  # Ya no pasamos poppler_path
        st.success(f"Se generaron {len(images)} imágenes del PDF")
        for i, img in enumerate(images):
            st.image(img, caption=f"Página {i+1}")
    except Exception as e:
        st.error(f"Error al convertir PDF a imágenes: {e}")
