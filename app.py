import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import re
import io
from collections import defaultdict

st.set_page_config(page_title="Factura Endesa a Excel", layout="centered")

st.title("📄 Convertidor PDF → Excel: Factura Endesa")

uploaded_file = st.file_uploader("Sube tu factura en PDF", type=["pdf"])

def extraer_periodos_energia(texto):
    """
    Extrae los kWh para P1–P6 manejando correctamente el formato 7.200,580 kWh.
    """
    patron = r"(P[1-6]):\s*([\d.,]+)\s*kWh"
    encontrados = re.findall(patron, texto)

    periodos = defaultdict(float)
    for periodo, valor in encontrados:
        # Eliminar puntos de miles y cambiar coma decimal por punto
        valor_limpio = valor.replace('.', '').replace(',', '.')
        try:
            valor_kwh = float(valor_limpio)
            if periodos[periodo] == 0.0:
                periodos[periodo] = valor_kwh
        except ValueError:
            continue  # Saltar si no se puede convertir

    return {f"{p} (kWh)": v for p, v in sorted(periodos.items())}

if uploaded_file is not None:
    # Leer texto del PDF
    with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
        texto = ""
        for page in doc:
            texto += page.get_text()

    st.success("✅ PDF procesado correctamente")

    # Extraer energía por periodo
    periodos_kwh = extraer_periodos_energia(texto)
    consumo_total = sum(periodos_kwh.values())

    # Crear DataFrame
    data = {**periodos_kwh, "Consumo Total (kWh)": consumo_total}
    df = pd.DataFrame([data])

    # Eliminar columnas duplicadas si las hay
    df = df.loc[:, ~df.columns.duplicated()]

    # Mostrar tabla
    st.subheader("📊 Resumen Detectado")
    st.dataframe(df, use_container_width=True)

    # Generar archivo Excel
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



