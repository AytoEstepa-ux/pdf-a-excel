import streamlit as st 
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Factura PDF a Excel", layout="centered")
st.title("📄 Extraer datos por periodo de factura PDF")

archivo_pdf = st.file_uploader("Subir factura PDF", type="pdf")

def extraer_periodo_facturacion(texto):
    # Expresión regular mejorada: acepta mayúsculas, espacios variables y tilde en facturación
    match = re.search(r"Periodo\s+facturaci[oó]n[:\s]+(\d{2}/\d{2}/\d{4})\s*al\s*(\d{2}/\d{2}/\d{4})", texto, re.IGNORECASE)
    return f"{match.group(1)} al {match.group(2)}" if match else None

def extraer_total_factura(texto):
    match = re.search(r"Total Factura\s+([\d.,]+)", texto, re.IGNORECASE)
    return match.group(1) if match else None

def extraer_por_periodo(texto):
    bloques = re.findall(
        r"Periodo (\d)\s+([\d.,]+)\s+([\d.,]+)\s+[\d.,]+\s+[\d.,]+\s+[\d.,]+\s+([\d.,]+)\s+([\d.,]+)\s+[\d.,]+\s+[\d.,]+\s+[\d.,]+\s+([\d.,]+)",
        texto
    )

    datos = []
    for b in bloques:
        datos.append({
            "Periodo": f"P{b[0]}",
            "Energía Activa (kWh)": b[1],
            "Energía Reactiva (kVArh)": b[2],
            "Potencia Contratada (kW)": b[3],
            "Potencia Máxima (kW)": b[4],
            "Importe Potencia (€)": b[5]
        })
    return datos

if archivo_pdf:
    texto = ""
    with pdfplumber.open(archivo_pdf) as pdf:
        for pagina in pdf.pages:
            texto += pagina.extract_text() + "\n"

    # Mostrar el texto extraído para depuración
    st.write("=== TEXTO EXTRAÍDO DEL PDF ===")
    st.write(texto)

    # Extracción de datos
    datos_periodo = extraer_por_periodo(texto)
    total_factura = extraer_total_factura(texto)
    periodo_facturacion = extraer_periodo_facturacion(texto)

    st.write("Periodo de facturación extraído:", periodo_facturacion)

    if datos_periodo:
        # Crear DataFrame
        df = pd.DataFrame(datos_periodo)

        # Asegurar que los nombres de columnas sean únicos
        df.columns = [str(col).strip() for col in df.columns]

        # Convertir "Importe Potencia (€)" a numérico para sumar
        df["Importe Potencia (€)"] = df["Importe Potencia (€)"].str.replace('.', '', regex=False).str.replace(',', '.', regex=False).astype(float)
        total_potencia = df["Importe Potencia (€)"].sum()

        # Agregar columna de Periodo de Facturación (igual para todos los registros)
        df["Periodo de Facturación"] = periodo_facturacion if periodo_facturacion else ""

        # Fila de totales (incluye total de potencia y total factura general)
        fila_total = {
            "Periodo": "TOTAL",
            "Energía Activa (kWh)": "",
            "Energía Reactiva (kVArh)": "",
            "Potencia Contratada (kW)": "",
            "Potencia Máxima (kW)": "",
            "Importe Potencia (€)": total_potencia,
            "Periodo de Facturación": "TOTAL FACTURA: " + (total_factura if total_factura else "")
        }
        df = pd.concat([df, pd.DataFrame([fila_total])], ignore_index=True)

        # Mostrar DataFrame en Streamlit
        df_display = df.copy()
        df_display["Importe Potencia (€)"] = df_display["Importe Potencia (€)"].apply(
            lambda x: f"{x:,.2f}".replace(".", ",") if isinstance(x, float) else x
        )

        st.subheader("📊 Datos por periodo")
        st.dataframe(df_display)

        if periodo_facturacion:
            st.markdown(f"📆 **Periodo de facturación:** {periodo_facturacion}")
        if total_factura:
            st.markdown(f"🧾 **Total factura general:** {total_factura} €")

        # Exportar a Excel
        salida_excel = BytesIO()
        df_display.to_excel(salida_excel, index=False, engine='openpyxl')
        salida_excel.seek(0)

        st.download_button(
            label="⬇️ Descargar Excel",
            data=salida_excel,
            file_name="factura_periodos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.error("❌ No se encontraron datos por periodo en el PDF.")
