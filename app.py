import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import re
import io

st.title("📄 Convertidor PDF → Excel: Factura Endesa")

uploaded_file = st.file_uploader("Sube tu factura en PDF", type=["pdf"])

def extraer_periodos_energia(texto):
    """
    Busca todos los patrones del tipo: Pn: NNNNN,NNN kWh
    Devuelve un diccionario con los periodos y sus valores en kWh
    """
    patron = r"(P[1-6]):\s*([\d.]+)[\s]*kWh"
    resultados = re.findall(patron, texto)
    
    periodos = {}
    for periodo, valor in resultados:
        kwh = float(valor.replace('.', '').replace(',', '.'))  # Convertir a float
        periodos[f"{periodo} (kWh)"] = kwh

    return periodos

if uploaded_file is not None:
    with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
        texto = ""
        for page in doc:
            texto += page.get_text()

    st.success("PDF procesado correctamente ✅")

    # Extraer kWh por periodo
    periodos_kwh = extraer_periodos_energia(texto)
    consumo_total = sum(periodos_kwh.values())

    # Construir DataFrame
    data = {**periodos_kwh, "Consumo Total (kWh)": consumo_total}
    df = pd.DataFrame([data])

    st.dataframe(df)

    # Generar Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Resumen Consumo", index=False)
    output.seek(0)

    # Botón de descarga
    st.download_button(
        label="⬇️ Descargar Excel",
        data=output,
        file_name="resumen_factura.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )





