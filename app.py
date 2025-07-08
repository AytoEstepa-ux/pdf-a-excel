import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Factura PDF a Excel", layout="centered")
st.title("📄 Extraer datos por periodo de factura PDF")

archivo_pdf = st.file_uploader("Subir factura PDF", type="pdf")

def parse_line_fixed_width(line, positions):
    """Extrae columnas de una línea con posiciones fijas.
    positions = lista de índices donde termina cada columna."""
    cols = []
    start = 0
    for pos in positions:
        cols.append(line[start:pos].strip())
        start = pos
    cols.append(line[start:].strip())
    return cols

def limpiar_numeros(text):
    # Reemplaza punto por nada, coma por punto para formato decimal europeo
    text = text.replace('.', '').replace(',', '.')
    try:
        return float(text)
    except:
        return None

if archivo_pdf:
    with pdfplumber.open(archivo_pdf) as pdf:
        texto = ""
        for pagina in pdf.pages:
            texto += pagina.extract_text() + "\n"

    lineas = texto.splitlines()

    # Variables para guardar tablas
    energia_lines = []
    potencia_lines = []

    leyendo_energia = False
    leyendo_potencia = False

    for linea in lineas:
        if "Energía" in linea:
            leyendo_energia = True
            leyendo_potencia = False
            continue
        if "Potencia" in linea:
            leyendo_potencia = True
            leyendo_energia = False
            continue

        if leyendo_energia:
            if "TOTAL" in linea or linea.strip() == "":
                leyendo_energia = False
                continue
            energia_lines.append(linea)

        elif leyendo_potencia:
            if "TOTAL" in linea or linea.strip() == "":
                leyendo_potencia = False
                continue
            potencia_lines.append(linea)

    # Ejemplo de posiciones fijas (ajustar según PDF)
    # Supongamos que en energía hay 5 columnas y en potencia 6 columnas
    # Estas posiciones son caracteres donde termina cada columna
    energia_pos = [10, 25, 40, 55]  # ej. ajustar según formato real
    potencia_pos = [10, 25, 40, 55, 70]  # ajustar

    # Parsear energía
    energia_data = []
    for l in energia_lines:
        cols = parse_line_fixed_width(l, energia_pos)
        if len(cols) == 5:
            energia_data.append(cols)

    # Parsear potencia
    potencia_data = []
    for l in potencia_lines:
        cols = parse_line_fixed_width(l, potencia_pos)
        if len(cols) == 6:
            potencia_data.append(cols)

    # Convertir a DataFrames
    df_energia = pd.DataFrame(energia_data, columns=[
        "Periodo", "Energía Activa (kWh)", "Energía Reactiva (kVArh)", "Excesos (kVArh)", "Importe Energía (€)"
    ])

    df_potencia = pd.DataFrame(potencia_data, columns=[
        "Periodo", "Potencia Contratada (kW)", "Potencia Máxima (kW)", "Excesos (kW)", "Importe Excesos Potencia (€)", "Extra"
    ])

    # Limpiar números
    for col in df_energia.columns[1:]:
        df_energia[col] = df_energia[col].apply(limpiar_numeros)

    for col in df_potencia.columns[1:-1]:  # excluir columna extra si no se usa
        df_potencia[col] = df_potencia[col].apply(limpiar_numeros)

    # Unir por periodo
    df = pd.merge(df_energia, df_potencia.drop(columns=['Extra']), on="Periodo", how="outer")

    # Calcular totales
    fila_total = {
        "Periodo": "TOTAL",
        "Energía Activa (kWh)": df["Energía Activa (kWh)"].sum(),
        "Energía Reactiva (kVArh)": df["Energía Reactiva (kVArh)"].sum(),
        "Excesos (kVArh)": df["Excesos (kVArh)"].sum(),
        "Importe Energía (€)": df["Importe Energía (€)"].sum(),
        "Potencia Contratada (kW)": "",
        "Potencia Máxima (kW)": "",
        "Excesos (kW)": df["Excesos (kW)"].sum(),
        "Importe Excesos Potencia (€)": df["Importe Excesos Potencia (€)"].sum(),
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






