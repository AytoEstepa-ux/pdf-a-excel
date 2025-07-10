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
    patron = r"ENERGÍA\s+ACTIVA\s+kWh\s*(P[1-6].*?)ENERGÍA\s+REACTIVA"
    match = re.search(patron, texto, re.DOTALL)
    datos = []

    if match:
        st.write(f"✅ Energía activa encontrada en {nombre_archivo}")
        lineas = match.group(1).strip().split("P")[1:]
        for i, linea in enumerate(lineas):
            partes = linea.strip().split()
            if len(partes) >= 7:
                periodo = f"P{i+1}"
                try:
                    consumo = float(partes[-1].replace('.', '').replace(',', '.'))
                except ValueError:
                    consumo = 0.0
                datos.append({
                    "Archivo": nombre_archivo,
                    "Periodo desde": periodo_desde,
                    "Periodo hasta": periodo_hasta,
                    "Periodo": periodo,
                    "Consumo (kWh)": consumo,
                    "Tipo Lectura": "Estimada"
                })
    else:
        st.warning(f"❌ No se encontró Energía Activa en {nombre_archivo}")

    return pd.DataFrame(datos)

def extraer_reactiva_inducida(texto, periodo_desde, periodo_hasta, nombre_archivo):
    datos = []
    try:
        # Cortamos desde el título hasta el siguiente bloque
        inicio = texto.find("ENERGÍA REACTIVA INDUCTIVA kWh")
        if inicio == -1:
            st.warning(f"❌ Energía reactiva inductiva no encontrada en {nombre_archivo}")
            return pd.DataFrame()

        bloque = texto[inicio:]
        fin = bloque.find("EXCESOS DE POTENCIA")
        if fin != -1:
            bloque = bloque[:fin]

        lineas = re.findall(r"P[1-6]\s+\d+\s+[\d,\.]+\s+\d+", bloque)

        if not lineas:
            st.info(f"ℹ️ Energía reactiva inductiva sin valores claros en {nombre_archivo}")
            return pd.DataFrame()

        for linea in lineas:
            partes = linea.strip().split()
            if len(partes) == 4:
                periodo = partes[0]
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
                    "Periodo": periodo,
                    "Consumo Reactiva (kWh)": consumo,
                    "Cos φ": cos_phi,
                    "A facturar Reactiva (€)": a_facturar
                })

        st.success(f"✅ Energía reactiva inductiva extraída correctamente de {nombre_archivo}")
        return pd.DataFrame(datos)

    except Exception as e:
        st.error(f"Error al procesar Energía Reactiva Inductiva en {nombre_archivo}: {e}")
        return pd.DataFrame()

def extraer_excesos_potencia(texto, periodo_desde, periodo_hasta, nombre_archivo):
    patron = r"EXCESOS\s+DE\s+POTENCIA\s+kW\s*Periodo horario.*?A facturar\s*(P[1-6].*?)INFORMACIÓN"
    match = re.search(patron, texto, re.DOTALL)
    datos = []

    if match:
        st.write(f"✅ Excesos de potencia encontrados en {nombre_archivo}")
        lineas = match.group(1).strip().split("P")[1:]
        for i, linea in enumerate(lineas):
            partes = linea.strip().split()
            if len(partes) >= 4:
                periodo = f"P{i+1}"
                try:
                    contratada = float(partes[1].replace('.', '').replace(',', '.'))
                    demandada = float(partes[2].replace('.', '').replace(',', '.'))
                    a_facturar = float(partes[3].replace('.', '').replace(',', '.'))
                except ValueError:
                    contratada = demandada = a_facturar = 0.0

                datos.append({
                    "Archivo": nombre_archivo,
                    "Periodo desde": periodo_desde,
                    "Periodo hasta": periodo_hasta,
                    "Periodo": periodo,
                    "Contratada (kW)": contratada,
                    "Demandada (kW)": demandada,
                    "A facturar Exceso (€)": a_facturar
                })
    else:
        st.warning(f"❌ No se encontró Excesos de Potencia en {nombre_archivo}")

    return pd.DataFrame(datos)

# ---------------------- EXPORTAR A EXCEL ----------------------
def generar_excel_acumulado(df_resumenes, df_activa, df_reactiva, df_excesos):
    # Convertir fechas a datetime para ordenar
    for df in [df_resumenes, df_activa, df_reactiva, df_excesos]:
        if "Periodo desde" in df.columns:
            df["Periodo desde"] = pd.to_datetime(df["Periodo desde"], format="%d/%m/%Y", errors='coerce')

    df_resumenes.sort_values("Periodo desde", inplace=True)
    df_activa.sort_values("Periodo desde", inplace=True)
    df_reactiva.sort_values("Periodo desde", inplace=True)
    df_excesos.sort_values("Periodo desde", inplace=True)

    # Volver a mostrar las fechas en formato dd/mm/yyyy
    for df in [df_resumenes, df_activa, df_reactiva, df_excesos]:
        if "Periodo desde" in df.columns:
            df["Periodo desde"] = df["Periodo desde"].dt.strftime("%d/%m/%Y")

    total_kwh = df_activa.groupby("Archivo")["Consumo (kWh)"].sum().reset_index()
    total_kwh.rename(columns={"Consumo (kWh)": "Total Consumo (kWh)"}, inplace=True)

    if not df_reactiva.empty and "A facturar Reactiva (€)" in df_reactiva.columns:
        total_reactiva = df_reactiva.groupby("Archivo")["A facturar Reactiva (€)"].sum().reset_index()
    else:
        total_reactiva = pd.DataFrame(columns=["Archivo", "Total Reactiva Inductiva (€)"])
    total_reactiva.rename(columns={"A facturar Reactiva (€)": "Total Reactiva Inductiva (€)"}, inplace=True)

    if not df_excesos.empty and "A facturar Exceso (€)" in df_excesos.columns:
        total_excesos = df_excesos.groupby("Archivo")["A facturar Exceso (€)"].sum().reset_index()
    else:
        total_excesos = pd.DataFrame(columns=["Archivo", "Total Excesos Potencia (€)"])
    total_excesos.rename(columns={"A facturar Exceso (€)": "Total Excesos Potencia (€)"}, inplace=True)

    df_totales = pd.merge(total_kwh, total_reactiva, on="Archivo", how="outer")
    df_totales = pd.merge(df_totales, total_excesos, on="Archivo", how="outer")
    df_totales = df_totales.fillna(0)

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
    resumenes, activas, reactivas, excesos = [], [], [], []

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

    df_totales = pd.DataFrame()
    excel_bytes = generar_excel_acumulado(df_resumenes, df_activas, df_reactivas, df_excesos)

    st.success("✅ Archivos procesados correctamente.")

    st.subheader("📊 Resumen general")
    st.dataframe(df_resumenes)

    st.subheader("⚡ Energía activa")
    st.dataframe(df_activas)

    st.subheader("🔁 Energía reactiva inductiva")
    st.dataframe(df_reactivas)

    st.subheader("📈 Excesos potencia")
    st.dataframe(df_excesos)

    st.subheader("📌 Totales por archivo")
    st.dataframe(pd.read_excel(io.BytesIO(excel_bytes), sheet_name="Totales por Archivo"))

    st.download_button(
        label="📅 Descargar Excel acumulado",
        data=excel_bytes,
        file_name="facturas_acumuladas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
