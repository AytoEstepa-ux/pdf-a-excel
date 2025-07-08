import streamlit as st
import pdfplumber
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Factura PDF a Excel", layout="centered")
st.title("📄 Extraer datos por periodo de factura PDF")

archivo_pdf = st.file_uploader("Subir factura PDF", type="pdf")

def limpiar_texto(df):
    # Eliminar filas vacías o con NaN
    df = df.dropna(how='all')
    # Reemplazar puntos y comas para decimales en numéricos
    for col in df.columns[1:]:  # saltar columna periodo
        df[col] = df[col].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

if archivo_pdf:
    with pdfplumber.open(archivo_pdf) as pdf:
        # Ejemplo: suponemos que la tabla de energía está en la página 1 y potencia en la página 2
        # Puedes ajustar el índice o buscar en todas las páginas
        
        # Extraer tablas de la primera página
        tablas_pagina_1 = pdf.pages[0].extract_tables()
        # Extraer tablas de la segunda página
        tablas_pagina_2 = pdf.pages[1].extract_tables() if len(pdf.pages) > 1 else []

    # Convertir las tablas extraídas en DataFrames pandas
    # Ajusta estos índices según tu PDF (a veces la tabla correcta no es la primera)
    df_energia = pd.DataFrame(tablas_pagina_1[0]) if tablas_pagina_1 else pd.DataFrame()
    df_potencia = pd.DataFrame(tablas_pagina_2[0]) if tablas_pagina_2 else pd.DataFrame()

    # Asignar nombres a columnas si no están (ajusta nombres según tu tabla)
    if not df_energia.empty:
        df_energia.columns = ["Periodo", "Energía Activa (kWh)", "Energía Reactiva (kVArh)", "Excesos (kVArh)", "Importe Energía (€)"]
        df_energia = limpiar_texto(df_energia)

    if not df_potencia.empty:
        df_potencia.columns = ["Periodo", "Potencia Contratada (kW)", "Potencia Máxima (kW)", "Excesos (kW)", "Importe Excesos Potencia (€)", "Otra Columna"]
        df_potencia = limpiar_texto(df_potencia)

    if not df_energia.empty and not df_potencia.empty:
        # Unir tablas por periodo
        df = pd.merge(df_energia, df_potencia, on="Periodo", how="outer")

        # Calcular totales
        fila_total = {
            "Periodo": "TOTAL",
            "Energía Activa (kWh)": df["Energía Activa (kWh)"].sum(),
            "Energía Reactiva (kVArh)": df["Energía Reactiva (kVArh)"].sum(),
            "Excesos (kVArh)": df["Excesos (kVArh)"].sum(),
            "Importe Energía (€)": df["Importe Energía (€)"].sum(),
            "Potencia Contratada (kW)": "",  # no suma
            "Potencia Máxima (kW)": "",      # no suma
            "Excesos (kW)": df["Excesos (kW)"].sum(),
            "Importe Excesos Potencia (€)": df["Importe Excesos Potencia (€)"].sum(),
            "Otra Columna": ""
        }
        df = pd.concat([df, pd.DataFrame([fila_total])], ignore_index=True)

        st.dataframe(df)

        salida_excel = BytesIO()
        df.to_excel(salida_excel, index=False, engine='openpyxl')
        salida_excel.seek(0)

        st.download_button(
            label="⬇️ Descargar Excel",
            data=salida_excel,
            file_name="factura_periodos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.error("No se pudieron extraer las tablas de energía y potencia.")




