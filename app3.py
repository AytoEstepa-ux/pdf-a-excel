import streamlit as st
import fitz  # PyMuPDF
import pandas as pd
import re
import io

# ---------------------- LECTURA PDF ----------------------

def leer_texto_pdf(file):
    with fitz.open(stream=file.read(), filetype="pdf") as doc:
        texto = ""
        for page in doc:
            texto += page.get_text()
    return texto

# ---------------------- EXTRACCIÓN DE DATOS ----------------------

def extraer_resumen_factura(texto):
    campos = {
        "Nº Factura": r"Nº de factura:\s*(\w+)",
        "Fecha emisión": r"Fecha emisión factura:\s*(\d{2}/\d{2}/\d{4})",
        "Periodo desde": r"del\s*(\d{2}/\d{2}/\d{4})",
        "Periodo hasta": r"al\s*(\d{2}/\d{2}/\d{4})",
        "Importe total (€)": r"IMPORTE\s+FACTURA[:\s]*([\d.,]+)",
        "Cliente": r"Cliente\s+([A-ZÁÉÍÓÚÑ .,\d]+)",
        "Dirección suministro": r"Dirección de suministro:\s*(.+?),",
        "CUPS": r"CUPS:\s*([A-Z0-9]+)",
        "Contrato Nº": r"Referencia del contrato:\s*(\d+)"
    }

    datos = {}
    for clave, patron in campos.items():
        match = re.search(patron, texto)
        datos[clave] = match.group(1).strip() if match else ""
    return pd.DataFrame([datos])

def extraer_energia_activa(texto, periodo_desde, periodo_hasta, nombre_archivo):
    match = re.search(r"ENERGÍA ACTIVA kWh([\s\S]+?)ENERGÍA REACTIVA kVArh", texto, re.IGNORECASE)
    datos = []

    lectura_match = re.search(r"Lectura\s+Lectura\s*\n\s*(real|estimada)\s+(real|estimada)", texto, re.IGNORECASE)
    lectura_tipos = lectura_match.groups() if lectura_match else ("", "")

    if match:
        for idx, linea in enumerate(match.group(1).splitlines()):
            m = re.search(r"P(\d)\s+\S+\s+[\d.,]+\s+[\d.,]+\s+[\d.,]+\s+[\d.,]+\s+([\d.,]+)", linea)
            if m:
                periodo = f"P{m.group(1)}"
                consumo = float(m.group(2).replace('.', '').replace(',', '.'))
                tipo_lectura = lectura_tipos[idx] if idx < len(lectura_tipos) else ""
                datos.append({
                    "Archivo": nombre_archivo,
                    "Periodo desde": periodo_desde,
                    "Periodo hasta": periodo_hasta,
                    "Periodo": periodo,
                    "Consumo (kWh)": consumo,
                    "Tipo Lectura": tipo_lectura.capitalize()
                })

    return pd.DataFrame(datos)

def extraer_reactiva_inducida(texto, periodo_desde, periodo_hasta, nombre_archivo):
    match = re.search(r"ENERGÍA REACTIVA INDUCTIVA kWh([\s\S]+?)EXCESOS DE POTENCIA", texto, re.IGNORECASE)
    datos = []
    if match:
        for linea in match.group(1).splitlines():
            m = re.search(r"P(\d)\s+([\d.,]+)\s+[\d.,]+\s+([\d.,]+)", linea)
            if m:
                datos.append({
                    "Archivo": nombre_archivo,
                    "Periodo desde": periodo_desde,
                    "Periodo hasta": periodo_hasta,
                    "Periodo": f"P{m.group(1)}",
                    "Consumo (kVArh)": float(m.group(2).replace('.', '').replace(',', '.')),
                    "A facturar (€)": float(m.group(3).replace('.', '').replace(',', '.'))
                })
    return pd.DataFrame(datos)

def extraer_excesos_potencia(texto, periodo_desde, periodo_hasta, nombre_archivo):
    match = re.search(r"EXCESOS DE POTENCIA kW([\s\S]+?)INFORMACIÓN DE SU PRODUCTO", texto, re.IGNORECASE)
    datos = []
    if match:
        for linea in match.group(1).splitlines():
            m = re.search(r"P(\d)\s+[\d.,]+\s+[\d.,]+\s+([\d.,]+)", linea)
            if m:
                datos.append({
                    "Archivo": nombre_archivo,
                    "Periodo desde": periodo_desde,
                    "Periodo hasta": periodo_hasta,
                    "Periodo": f"P{m.group(1)}",
                    "A facturar (kW)": float(m.group(2).replace('.', '').replace(',', '.'))
                })
    return pd.DataFrame(datos)

# ---------------------- EXPORTAR A EXCEL ----------------------

def generar_excel_acumulado(df_resumenes, df_activa, df_reactiva, df_excesos):
    # Inicializar totales vacíos
    total_kwh = pd.DataFrame(columns=["Archivo", "Total Consumo (kWh)"])
    total_reactiva = pd.DataFrame(columns=["Archivo", "Total Reactiva (€)"])
    total_excesos = pd.DataFrame(columns=["Archivo", "Total Excesos (kW)"])

    if not df_activa.empty and "Archivo" in df_activa.columns:
        total_kwh = df_activa.groupby("Archivo")["Consumo (kWh)"].sum().reset_index()
        total_kwh.rename(columns={"Consumo (kWh)": "Total Consumo (kWh)"}, inplace=True)

    if not df_reactiva.empty and "Archivo" in df_reactiva.columns:
        total_reactiva = df_reactiva.groupby("Archivo")["A facturar (€)"].sum().reset_index()
        total_reactiva.rename(columns={"A facturar (€)": "Total Reactiva (€)"}, inplace=True)

    if not df_excesos.empty and "Archivo" in df_excesos.columns:
        total_excesos = df_excesos.groupby("Archivo")["A facturar (kW)"].sum().reset_index()
        total_excesos.rename(columns={"A facturar (kW)": "Total Excesos (kW)"}, inplace=True)

    # Unir todos los totales por archivo
    df_totales = pd.merge(total_kwh, total_reactiva, on="Archivo", how="outer")
    df_totales = pd.merge(df_totales, total_excesos, on="Archivo", how="outer")
    df_totales = df_totales.fillna(0)

    # Crear archivo Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_resumenes.to_excel(writer, sheet_name="Resumen Factura", index=False)
        df_activa.to_excel(writer, sheet_name="Energía Activa", index=False)
        df_reactiva.to_excel(writer, sheet_name="Energía Reactiva", index=False)
        df_excesos.to_excel(writer, sheet_name="Excesos Potencia", index=False)
        df_totales.to_excel(writer, sheet_name="Totales por Archivo", index=False)
    return output.getvalue()

# ---------------------- STREAMLIT APP ----------------------

st.set_page_config(page_title="Facturas Eléctricas", layout="wide")
st.title("🔄 Procesador de múltiples facturas eléctricas")

archivos = st.file_uploader("📁 Sube varios archivos PDF", type="pdf", accept_multiple_files=True)

if archivos:
    resumenes = []
    activas = []
    reactivas = []
    excesos = []

    for archivo in archivos:
        texto = leer_texto_pdf(archivo)
        nombre_archivo = archivo.name

        df_resumen = extraer_resumen_factura(texto)
        periodo_desde = df_resumen.at[0, "Periodo desde"]
        periodo_hasta = df_resumen.at[0, "Periodo hasta"]
        df_resumen["Archivo"] = nombre_archivo
        resumenes.append(df_resumen)

        df_activa = extraer_energia_activa(texto, periodo_desde, periodo_hasta, nombre_archivo)
        activas.append(df_activa)

        df_reactiva = extraer_reactiva_inducida(texto, periodo_desde, periodo_hasta, nombre_archivo)
        reactivas.append(df_reactiva)

        df_exceso = extraer_excesos_potencia(texto, periodo_desde, periodo_hasta, nombre_archivo)
        excesos.append(df_exceso)

    df_resumenes = pd.concat(resumenes, ignore_index=True)
    df_activas = pd.concat(activas, ignore_index=True)
    df_reactivas = pd.concat(reactivas, ignore_index=True)
    df_excesos = pd.concat(excesos, ignore_index=True)

    st.success("✅ Archivos procesados correctamente.")

    st.subheader("📊 Resumen general")
    st.dataframe(df_resumenes)

    st.subheader("⚡ Energía activa")
    st.dataframe(df_activas)

    st.subheader("🔁 Energía reactiva")
    st.dataframe(df_reactivas)

    st.subheader("📈 Excesos potencia")
    st.dataframe(df_excesos)

    excel_bytes = generar_excel_acumulado(df_resumenes, df_activas, df_reactivas, df_excesos)

    st.download_button(
        label="📅 Descargar Excel acumulado",
        data=excel_bytes,
        file_name="facturas_acumuladas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
