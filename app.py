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

    datos_periodo = extraer_por_periodo(texto)
    total_factura = extraer_total_factura(texto)
    periodo_facturacion = extraer_periodo_facturacion(texto)

    if datos_periodo:
        # Crear DataFrame
        df = pd.DataFrame(datos_periodo)

        # Asegurar columnas únicas (por seguridad)
        df.columns = pd.io.parsers.ParserBase({'names': df.columns})._maybe_dedup_names(df.columns)

        # Convertir importe a float
        df["Importe Potencia (€)"] = df["Importe Potencia (€)"].str.replace('.', '', regex=False).str.replace(',', '.', regex=False).astype(float)
        total_potencia = df["Importe Potencia (€)"].sum()

        # Fila total
        fila_total = {
            "Periodo": "TOTAL",
            "Energía Activa (kWh)": "",
            "Energía Reactiva (kVArh)": "",
            "Potencia Contratada (kW)": "",
            "Potencia Máxima (kW)": "",
            "Importe Potencia (€)": total_potencia
        }
        df = pd.concat([df, pd.DataFrame([fila_total])], ignore_index=True)

        # Si ya existe la columna "Periodo de Facturación", eliminarla
        if "Periodo de Facturación" in df.columns:
            df = df.d
