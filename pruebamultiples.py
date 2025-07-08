import streamlit as st

st.title("Carga de múltiples PDFs")

# Cargar múltiples archivos PDF
uploaded_files = st.file_uploader("Sube tus archivos PDF", type=["pdf"], accept_multiple_files=True)

if uploaded_files is not None:
    st.write(f"Has subido {len(uploaded_files)} archivos PDF:")
    for uploaded_file in uploaded_files:
        st.write(uploaded_file.name)
else:
    st.write("No se ha subido ningún archivo.")
