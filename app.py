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

def hacer_nombres_columnas_unicos_
