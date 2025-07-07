import streamlit as st
import pdfplumber
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="PDF a Excel", layout="centered")
st.title("📄 Convertir PDF a Excel")

st.write("Sube un archivo PDF con una tabla, y convierte los datos a Excel automáticamente.")

archivo_pdf = st.file_uploader("Subir PDF", type="pdf")

if archivo_pdf:
    datos = []

    with pdfplumber.open(archivo_pdf) as pdf:
        for pagina in pdf.pages:
            tabla = pagina.extract_table()
            if tabla:
                datos.extend(tabla)

    if datos:
        df = pd.DataFrame(datos[1:], columns=datos[0])
        st.dataframe(df)

        # Convertir a Excel en memoria
        salida_excel = BytesIO()
        df.to_excel(salida_excel, index=False, engine='openpyxl')
        salida_excel.seek(0)

        st.download_button(
            label="⬇️ Descargar Excel",
            data=salida_excel,
            file_name="datos_convertidos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.error("No se encontraron tablas en el PDF.")