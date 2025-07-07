import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Extraer datos factura PDF", layout="centered")
st.title("📄 Extraer datos clave de factura PDF")

st.write("Sube una factura PDF de electricidad y extraeré: Total factura, potencia, energía reactiva...")

archivo_pdf = st.file_uploader("Subir PDF", type="pdf")

def extraer_datos(texto):
    datos = {}

    # Buscar Total Factura
    total_factura = re.search(r'Total Factura\s+([\d.,]+)\s?€?', texto)
    if total_factura:
        datos["Total Factura (€)"] = total_factura.group(1)

    # Buscar Energía Reactiva Importe Total (se indica explícitamente como 0,00 €)
    energia_reactiva = re.search(r'energía reactiva\D+([\d.,]+)\s?€', texto)
    if energia_reactiva:
        datos["Energía Reactiva (€)"] = energia_reactiva.group(1)

    # Potencia Contratada (aparece varias veces, pero es constante: 150,000 kW)
    potencia_contratada = re.search(r'P1:\s*([\d.,]+)\s*kW', texto)
    if potencia_contratada:
        datos["Potencia Contratada (kW)"] = potencia_contratada.group(1)

    # Potencia Máxima Registrada (aparece al final en tabla de desglose)
    potencia_max = re.search(r'Max\.Reg\.\s+([\d.,]+)', texto)
    if potencia_max:
        datos["Potencia Máx. Registrada (kW)"] = potencia_max.group(1)

    # Importe Total Potencia = Potencia Contratada + Demandada
    importe_potencia_contratada = re.search(r'Fact\. Potencia Contratada.*?([\d.,]+)\s*Eur', texto, re.DOTALL)
    importe_potencia_demandada = re.search(r'Fact\. Potencia Demandada.*?([\d.,]+)\s*Eur', texto, re.DOTALL)

    if importe_potencia_contratada and importe_potencia_demandada:
        total_potencia = float(importe_potencia_contratada.group(1).replace('.', '').replace(',', '.')) + \
                         float(importe_potencia_demandada.group(1).replace('.', '').replace(',', '.'))
        datos["Importe Total Potencia (€)"] = f"{total_potencia:,.2f}".replace('.', ',')

    return datos

if archivo_pdf:
    texto_completo = ""
    with pdfplumber.open(archivo_pdf) as pdf:
        for pagina in pdf.pages:
            texto_completo += pagina.extract_text() + "\n"

    datos_extraidos = extraer_datos(texto_completo)

    if datos_extraidos:
        df = pd.DataFrame(list(datos_extraidos.items()), columns=["Concepto", "Valor"])
        st.dataframe(df)

        # Exportar a Excel
        salida_excel = BytesIO()
        df.to_excel(salida_excel, index=False, engine="openpyxl")
        salida_excel.seek(0)

        st.download_button(
            label="⬇️ Descargar Excel",
            data=salida_excel,
            file_name="datos_factura.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.error("No se pudieron extraer datos clave del texto del PDF.")
