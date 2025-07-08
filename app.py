import streamlit as st 
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Factura PDF a Excel", layout="centered")
st.title("📄 Extraer datos por periodo de factura PDF")

archivo_pdf = st.file_uploader("Subir factura PDF", type="pdf")

def extraer_periodo_facturacion(texto):
    match = re.search(r"Periodo facturación:\s+(\d{2}/\d{2}/\d{4})\s+al\s+(\d{2}/\d{2}/\d{4})", texto)
    return f"{match.group(1)} al {match.group(2)}" if match else None

def extraer_total_factura(texto):
    match = re.search(r"Total Factura\s+([\d.,]+)", texto)
    return match.group(1) if match else None

def extraer_por_periodo(texto):
    bloques = re.findall(
        r"Periodo\s+(\d).*?"                        # 0: Periodo
        r"([\d.,]+)\s+"                             # 1: Energía Activa (kWh)
        r"([\d.,]+)\s+"                             # 2: Energía Reactiva (kVArh)
        r"[\d.,]+\s+"                               # (cos phi, omitido)
        r"([\d.,]+)\s+"                             # 3: Importe Energía Reactiva (€)
        r"([\d.,]+)\s+"                             # 4: Potencia Contratada (kW)
        r"([\d.,]+)\s+"                             # 5: Potencia Máxima (kW)
        r"[\d.,]+\s+[\d.,]+\s+[\d.,]+\s+[\d.,]+\s+"  # saltar columnas intermedias
        r"([\d.,]+)",                               # 6: Importe Potencia (€)
        texto
    )

    datos = []
    for b in bloques:
        datos.append({
            "Periodo": f"P{b[0]}",
            "Energía Activa (kWh)": b[1],
            "Energía Reactiva (kVArh)": b[2],
            "Importe Energía Reactiva (€)": b[3],
            "Potencia Contratada (kW)": b[4],
            "Potencia Máxima (kW)": b[5],
            "Importe Potencia (€)": b[6]
        })
    return datos

if archivo_pdf:
    texto = ""
    with pdfplumber.open(archivo_pdf) as pdf:
        for pagina in pdf.pages:
            texto += pagina.extract_text() + "\n"

    datos_periodo = extraer_por_periodo(texto)
    total_factura = extraer_total_factura(texto)
    periodo_facturacion = extraer_periodo_facturacion(texto)

    if datos_periodo:
        df = pd.DataFrame(datos_periodo)

        # Limpiar nombres de columnas
        df.columns = [str(col).strip() for col in df.columns]

        # Convertir importes a float
        for col in ["Importe Potencia (€)", "Importe Energía Reactiva (€)"]:
            df[col] = df[col].str.replace('.', '', regex=False).str.replace(',', '.', regex=False).astype(float)

        total_potencia = df["Importe Potencia (€)"].sum()
        total_reactiva = df["Importe Energía Reactiva (€)"].sum()

        # Añadir columna del periodo de facturación
        df["Periodo de Facturación"] = periodo_facturacion if periodo_facturacion else ""

        # Añadir fila de totales
        fila_total = {
            "Periodo": "TOTAL",
            "Energía Activa (kWh)": "",
            "Energía Reactiva (kVArh)": "",
            "Importe Energía Reactiva (€)": total_reactiva,
            "Potencia Contratada (kW)": "",
            "Potencia Máxima (kW)": "",
            "Importe Potencia (€)": total_potencia,
            "Periodo de Facturación": "TOTAL FACTURA: " + (total_factura if total_factura else "")
        }
        df = pd.concat([df, pd.DataFrame([fila_total])], ignore_index=True)

        # Mostrar DataFrame formateado
        df_display = df.copy()
        for col in ["Importe Potencia (€)", "Importe Energía Reactiva (€)"]:
            df_display[col] = df_display[col].apply(
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
