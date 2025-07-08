import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import re
import io
from collections import defaultdict

st.set_page_config(page_title="Factura Endesa a Excel", layout="centered")

st.title("📄 Convertidor PDF → Excel: Factura Endesa")

uploaded_file = st.file_uploader("Sube tu factura en PDF", type=["pdf"])

# Función para extraer datos únicos por periodo
def extraer_periodos_energia(texto):
    patron = r"(P[1-6]):\s*([\d.]+)[\s]*kWh"
    encontrados = re.findall(patron, texto)

    periodos = defaultdict(float)
    for periodo, valor in encontrados:
        valor_kwh = float(valor.replace('.', '').replace(',', '.'))
        if periodos[periodo] == 0.0:  # evitar duplicados
            periodos[periodo] = valor_kwh

    return {f"{p} (kWh)": v for p, v in sorted(periodos.items())}

if uploaded_file is not None:
    with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
        texto = ""
        for page in doc:
            texto += page.get_text()

    st.success("✅ PDF procesado correctamente")

    # Extraer kWh por periodo
    periodos_kwh = extraer_periodos_energia(texto)
    consumo_total = sum(periodos_kwh.values())

    # Preparar DataFrame
    data = {**periodos_kwh, "Consumo Total (kWh)": consumo_total}
    df = pd.DataFrame([data])

    # Asegurar columnas únicas
    df.columns = pd.io.parsers.ParserBase({'names': df.columns})._maybe_dedup_names(df.columns)

    st.subheader("📊 Resumen Detectado")
    st.dataframe(df, use_container_width=True)

    # Generar Excel para descarga
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Resumen Consumo", index=False)
    output.seek(0)

    st.download_button(
        label="⬇️ Descargar Excel",
        data=output,
        file_name="resumen_factura.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )





