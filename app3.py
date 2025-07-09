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
    texto = texto.replace('\n', ' ')
    texto = re.sub(r'\s{2,}', ' ', texto)
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
    patron = r"ENERGÍA\s+ACTIVA\s+kWh\s+(.*?)ENERGÍA\s+REACTIVA"
    match = re.search(patron, texto, re.DOTALL)
    datos = []

    if match:
        st.write("✅ Se encontró bloque de energía activa.")
        lineas = match.group(1).strip().split("P")[1:]  # Omitimos lo que hay antes de P1
        for i, linea in enumerate(lineas):
            partes = linea.strip().split()
            if len(partes) >= 6:
                consumo = partes[-1].replace('.', '').replace(',', '.')
                try:
                    consumo = float(consumo)
                except ValueError:
                    consumo = 0.0
                datos.append({
                    "Archivo": nombre_archivo,
                    "Periodo desde": periodo_desde,
                    "Periodo hasta": periodo_hasta,
                    "Periodo": f"P{i+1}",
                    "Consumo (kWh)": consumo,
                    "Tipo Lectura": "Estimada"
                })
    else:
        st.warning(f"❌ No se encontró bloque de energía activa en {nombre_archivo}")

    return pd.DataFrame(datos)

def extraer_reactiva_inducida(texto, periodo_desde, periodo_hasta, nombre_archivo):
    patron = r"ENERGÍA\s+REACTIVA\s+INDUCTIVA\s+kWh\s+Periodo horario(.*?)EXCESOS\s+DE\s+POTENCIA"
    match = re.search(patron, texto, re.DOTALL)
    datos = []

    if match:
        st.write("✅ Se encontró bloque de energía reactiva inductiva.")
        lineas = match.group(1).strip().split("P")[1:]  # Omite cabecera
        for i, linea in enumerate(lineas):
            partes = linea.strip().split()
            if len(partes) >= 4:
                try:
                    consumo = float(partes[1].replace('.', '').replace(',', '.'))
                except ValueError:
                    consumo = 0.0
                try:
                    cos_phi = float(partes[2].replace(',', '.'))
                except ValueError:
                    cos_phi = 0.0
                try:
                    a_facturar = float(partes[3].replace('.', '').replace(',', '.'))
                except ValueError:
                    a_facturar = 0.0
                datos.append({
                    "Archivo": nombre_archivo,
                    "Periodo desde": periodo_desde,
                    "Periodo hasta": periodo_hasta,
                    "Periodo": f"P{i+1}",
                    "Consumo (kWh)": consumo,
                    "Cos φ": cos_phi,
                    "A facturar (€)": a_facturar
                })
    else:
        st.warning(f"❌ No se encontró bloque de energía reactiva inductiva en {nombre_archivo}")

    return pd.DataFrame(datos)


def extraer_excesos_potencia(texto, periodo_desde, periodo_hasta, nombre_archivo):
    patron = r"EXCESOS\s+DE\s+POTENCIA\s+kW\s+Periodo horario.*?Contratada.*?Demandada.*?A facturar(.*?)INFORMACIÓN\s+DE\s+SU\s+PRODUCTO"
    match = re.search(patron, texto, re.DOTALL)
    datos = []

    if match:
        st.write("✅ Se encontró bloque de excesos de potencia.")
        lineas = match.group(1).strip().split("P")[1:]  # Se omite cabecera y se procesan las líneas
        
        for linea in lineas:
            partes = linea.strip().split()
            if len(partes) >= 5:  # Al menos 5 partes (Periodo, Contratada, Demandada, A facturar)
                periodo = f"P{partes[0]}"
                
                try:
                    contratada = float(partes[1].replace('.', '').replace(',', '.'))
                except ValueError:
                    contratada = 0.0
                    
                try:
                    demandada = float(partes[2].replace('.', '').replace(',', '.'))
                except ValueError:
                    demandada = 0.0
                    
                try:
                    a_facturar = float(partes[4].replace('.', '').replace(',', '.'))
                except ValueError:
                    a_facturar = 0.0
                
                datos.append({
                    "Archivo": nombre_archivo,
                    "Periodo desde": periodo_desde,
                    "Periodo hasta": periodo_hasta,
                    "Periodo": periodo,
                    "Contratada (kW)": contratada,
                    "Demandada (kW)": demandada,
                    "A facturar (kW)": a_facturar
                })
    else:
        st.warning(f"❌ No se encontró bloque de excesos de potencia en {nombre_archivo}")

    return pd.DataFrame(datos)


# ---------------------- EXPORTAR A EXCEL ----------------------
def generar_excel_acumulado(df_resumenes, df_activa, df_reactiva, df_excesos):
    # Totales por archivo
    total_kwh = pd.DataFrame(columns=["Archivo", "Total Consumo (kWh)"])
    total_reactiva = pd.DataFrame(columns=["Archivo", "Total Reactiva Inductiva (€)"])
    total_excesos = pd.DataFrame(columns=["Archivo", "Total Excesos Potencia (€)"])

    if not df_activa.empty and "Archivo" in df_activa.columns:
        total_kwh = df_activa.groupby("Archivo")["Consumo (kWh)"].sum().reset_index()
        total_kwh.rename(columns={"Consumo (kWh)": "Total Consumo (kWh)"}, inplace=True)

    if not df_reactiva.empty and "Archivo" in df_reactiva.columns:
        total_reactiva = df_reactiva.groupby("Archivo")["A facturar (€)"].sum().reset_index()
        total_reactiva.rename(columns={"A facturar (€)": "Total Reactiva Inductiva (€)"}, inplace=True)

    if not df_excesos.empty and "Archivo" in df_excesos.columns:
        total_excesos = df_excesos.groupby("Archivo")["A facturar (kW)"].sum().reset_index()
        total_excesos.rename(columns={"A facturar (kW)": "Total Excesos Potencia (€)"}, inplace=True)

    # Unir totales
    df_totales = pd.merge(total_kwh, total_reactiva, on="Archivo", how="outer")
    df_totales = pd.merge(df_totales, total_excesos, on="Archivo", how="outer")
    df_totales = df_totales.fillna(0)

    # Crear Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_resumenes.to_excel(writer, sheet_name="Resumen Factura", index=False)
        df_activa.to_excel(writer, sheet_name="Energía Activa", index=False)
        df_reactiva.to_excel(writer, sheet_name="Energía Reactiva Inductiva", index=False)
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

        # Calculamos y mostramos los totales en pantalla
    total_kwh = df_activas.groupby("Archivo")["Consumo (kWh)"].sum().reset_index()
    total_reactiva = df_reactivas.groupby("Archivo")["A facturar (€)"].sum().reset_index()
    total_excesos = df_excesos.groupby("Archivo")["A facturar (kW)"].sum().reset_index()

    df_totales = pd.merge(total_kwh, total_reactiva, on="Archivo", how="outer")
    df_totales = pd.merge(df_totales, total_excesos, on="Archivo", how="outer")
    df_totales.columns = ["Archivo", "Total Consumo (kWh)", "Total Reactiva Inductiva (€)", "Total Excesos Potencia (€)"]
    df_totales = df_totales.fillna(0)

    st.success("✅ Archivos procesados correctamente.")

    st.subheader("📊 Resumen general")
    st.dataframe(df_resumenes)

    st.subheader("⚡ Energía activa")
    st.dataframe(df_activas)

    st.subheader("🔁 Energía reactiva")
    st.dataframe(df_reactivas)

    st.subheader("📈 Excesos potencia")
    st.dataframe(df_excesos)

    st.subheader("📌 Totales por archivo")
    st.dataframe(df_totales)


    excel_bytes = generar_excel_acumulado(df_resumenes, df_activas, df_reactivas, df_excesos)

    st.download_button(
        label="📅 Descargar Excel acumulado",
        data=excel_bytes,
        file_name="facturas_acumuladas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
