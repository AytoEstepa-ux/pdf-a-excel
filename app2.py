import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import re
import io
from collections import defaultdict

st.set_page_config(page_title="Factura Endesa a Excel", layout="centered")

st.title("📄 Convertidor PDF → Excel: Factura Endesa")

# Subir múltiples PDFs
uploaded_files = st.file_uploader("Sube tus facturas en PDF", type=["pdf"], accept_multiple_files=True)

def extraer_datos_generales(texto):
    campos = {
        "Factura nº": r"Factura nº:\s*([A-Z0-9]+)",
        "Fecha Factura": r"Fecha Factura:\s*([\d/]+)",
        "Periodo Facturación": r"Periodo facturación:\s*([\d/]+\s+al\s+[\d/]+)",
        "Total Factura": r"Total Factura\s*([\d.,]+)\s*€",
        "Cliente": r"Razón Social:\s*(.+)",
        "NIF/CIF": r"NIF/CIF:\s*([A-Z0-9]+)",
        "Dirección Fiscal": r"Dir\.Fiscal:\s*(.+)",
        "Dirección Suministro": r"Dir\.Suministro:\s*(.+)",
        "CUPS": r"CUPS:\s*([A-Z0-9]+)",
        "Contrato Nº": r"Contrato nº:\s*([0-9]+)",
        "Modalidad de Contrato": r"Modalidad de Contrato:\s*(.+)",
        "Fecha Límite de Pago": r"antes del\s*([\d/]+)"
    }

    resultados = {}
    for campo, patron in campos.items():
        match = re.search(patron, texto)
        resultados[campo] = match.group(1).strip() if match else ""

    return resultados

def extraer_tabla_energia_y_potencia(texto, periodo_facturacion):
    """
    Busca patrones del tipo P1 a P6 y extrae las cifras de energía y potencia por periodo.
    """
    patron = re.compile(
        r"Periodo\s+([1-6])(?:\s+Capacitiva)?\s+"  # P1 a P6
        r"([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+" 
        r"([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+" 
        r"([\d.,]+)"
    )

    filas = []
    for match in patron.finditer(texto):
        valores = [match.group(i).replace('.', '').replace(',', '.') for i in range(1, 13)]
        fila = {
            "Periodo Facturación": periodo_facturacion,
            "Periodo": f"P{valores[0]}",
            "Consumo kWh": float(valores[1]),
            "Reactiva (kVArh)": float(valores[2]),
            "Exceso Reactiva": float(valores[3]),
            "Cosφ": float(valores[4]),
            "Importe Reactiva (€)": float(valores[5]),
            "Potencia Contratada": float(valores[6]),
            "Max. Registrada": float(valores[7]),
            "Kp": float(valores[8]),
            "Te": float(valores[9]),
            "Excesos Potencia": float(valores[10]),
            "Importe Potencia (€)": float(valores[11]),
        }
        filas.append(fila)

    return pd.DataFrame(filas)

if uploaded_files:
    all_resumen = []
    all_detalle = []

    for uploaded_file in uploaded_files:
        with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
            texto = ""
            for page in doc:
                texto += page.get_text()

        st.success(f"✅ PDF procesado correctamente: {uploaded_file.name}")

        # Extraer datos generales
        resumen_dict = extraer_datos_generales(texto)
        df_resumen = pd.DataFrame([resumen_dict])
        all_resumen.append(df_resumen)

        # Extraer tabla por periodo
        periodo_facturacion = resumen_dict.get("Periodo Facturación", "Desconocido")
        df_detalle = extraer_tabla_energia_y_potencia(texto, periodo_facturacion)
        all_detalle.append(df_detalle)

    # Combinar todos los datos en un solo DataFrame
    df_resumen_total = pd.concat(all_resumen, ignore_index=True)
    df_detalle_total = pd.concat(all_detalle, ignore_index=True)

    # Mostrar los resultados
    st.subheader("📋 Resumen de todas las Facturas")
    st.dataframe(df_resumen_total)

    st.subheader("📊 Energía y Potencia por Periodo (Acumulado)")
    st.dataframe(df_detalle_total)

    # Generar Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_resumen_total.to_excel(writer, sheet_name="Resumen Factura", index=False)
        df_detalle_total.to_excel(writer, sheet_name="Energía y Potencia", index=False)
    output.seek(0)

    # Botón de descarga
    st.download_button(
        label="⬇️ Descargar Excel",
        data=output,
        file_name="facturas_endesa_acumuladas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )



