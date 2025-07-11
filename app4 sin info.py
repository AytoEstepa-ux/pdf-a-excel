import streamlit as st
import fitz            # PyMuPDF
import pandas as pd
import re
import io

# ---------------------- LECTURA PDF ----------------------
def leer_texto_pdf(file):
    """Devuelve el texto del PDF, colapsando saltos de línea y espacios extra."""
    with fitz.open(stream=file.read(), filetype="pdf") as doc:
        texto = " ".join(
            page.get_text()        # Si tuvieras columnas difíciles, prueba page.get_text("blocks")
            .replace("\n", " ")
            for page in doc
        )
    return re.sub(r"\s{2,}", " ", texto)

# ---------------------- EXTRACCIÓN DE DATOS ----------------------
def extraer_resumen_factura(texto):
    """Extrae los campos resumen según el nuevo formato de factura."""
    campos = {
        "Nº Factura"        : r"Factura Nº\s*([\w\-]+)",
        "Fecha emisión"     : r"Emisión\s*(\d{2}-\d{2}-\d{4})",
        "Periodo desde"     : r"Periodo\s*(\d{2}-\d{2}-\d{4})\s*>",
        "Periodo hasta"     : r">\s*(\d{2}-\d{2}-\d{4})",
        "Importe total (€)" : r"Total\s*\(€\)\s*([\d.,]+)",
        "Cliente"           : r"Cliente\s+([A-ZÁÉÍÓÚÑ .,\d]+)",
        "Dirección suministro": r"Suministro:\s*(.+?),\s*\d{5}",
        "CUPS"              : r"CUPS\s*([A-Z0-9]+)",
        "Contrato Nº"       : r"Contrato\s*(\d+)",
    }

    datos = {k: (m.group(1).strip() if (m := re.search(p, texto)) else "")
             for k, p in campos.items()}
    return pd.DataFrame([datos])


# ---------------------- BLOQUES VARIABLES ----------------------
def _recortar_hasta_siguiente_cabecera(bloque: str) -> str:
    """Corta el bloque en la primera línea de cabecera (mayúsculas largas)."""
    match = re.search(r"\n[A-ZÁÉÍÓÚÑ ]{10,}", bloque)
    return bloque[:match.start()] if match else bloque


# ---------------------- ENERGÍA ACTIVA ----------------------
def extraer_energia_activa(texto, periodo_desde, periodo_hasta, nombre_archivo):
    datos = []

    # Buscar bloque que comienza en "ENERGÍA ACTIVA kWh"
    inicio = texto.find("ENERGÍA ACTIVA kWh")
    if inicio == -1:
        st.warning(f"❌ No se encontró Energía Activa en {nombre_archivo}")
        return pd.DataFrame(columns=[
            "Archivo", "Periodo desde", "Periodo hasta",
            "Periodo", "Consumo (kWh)", "Tipo Lectura"
        ])

    # Tomamos bloque desde ese punto y lo cortamos si aparece otra sección
    bloque = texto[inicio:]
    bloque = _recortar_hasta_siguiente_cabecera(bloque)

    # Buscar todas las líneas tipo: P1 1.18.1 7275,00 7275,00 1,00 0,00 0,00
    lineas = re.findall(r"P([1-6])\s+[0-9.]+[\s,]+[\d.,]+\s+[\d.,]+\s+[\d.,]+\s+[\d.,]+\s+[\d.,]+", bloque)

    if not lineas:
        st.info(f"ℹ️ Energía Activa presente pero sin consumos claros en {nombre_archivo}")
        return pd.DataFrame(columns=[
            "Archivo", "Periodo desde", "Periodo hasta",
            "Periodo", "Consumo (kWh)", "Tipo Lectura"
        ])

    # Procesar las líneas con consumo
    for match in re.finditer(r"P([1-6])\s+[^\n]+?([\d.,]+)$", bloque, re.MULTILINE):
        periodo = f"P{match.group(1)}"
        try:
            consumo = float(match.group(2).replace('.', '').replace(',', '.'))
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

    if datos:
        st.success(f"✅ Energía activa extraída correctamente de {nombre_archivo}")
        return pd.DataFrame(datos)
    else:
        return pd.DataFrame(columns=[
            "Archivo", "Periodo desde", "Periodo hasta",
            "Periodo", "Consumo (kWh)", "Tipo Lectura"
        ])



# ---------------------- ENERGÍA REACTIVA INDUCTIVA ----------------------
def extraer_reactiva_inducida(texto, periodo_desde, periodo_hasta, nombre_archivo):
    datos = []
    try:
        inicio = texto.find("ENERGÍA REACTIVA INDUCTIVA kWh")
        if inicio == -1:
            st.warning(f"❌ Energía reactiva inductiva no encontrada en {nombre_archivo}")
            return pd.DataFrame(columns=[
                "Archivo", "Periodo desde", "Periodo hasta", "Periodo",
                "Consumo Reactiva (kWh)", "Cos φ", "A facturar Reactiva (€)"
            ])

        bloque = _recortar_hasta_siguiente_cabecera(texto[inicio:])
        lineas = re.findall(r"P[1-6]\s+[\d.,]+\s+[\d.,]+\s+[\d.,]+", bloque)

        if not lineas:
            st.info(f"ℹ️ Energía reactiva inductiva sin valores claros en {nombre_archivo}")
            return pd.DataFrame(columns=[
                "Archivo", "Periodo desde", "Periodo hasta", "Periodo",
                "Consumo Reactiva (kWh)", "Cos φ", "A facturar Reactiva (€)"
            ])

        for linea in lineas:
            m = re.match(
                r"P(?P<periodo>[1-6])\s+"
                r"(?P<consumo>[\d.,]+)\s+"
                r"(?P<cosphi>[\d.,]+)\s+"
                r"(?P<a_facturar>[\d.,]+)",
                linea
            )
            if m:
                datos.append({
                    "Archivo": nombre_archivo,
                    "Periodo desde": periodo_desde,
                    "Periodo hasta": periodo_hasta,
                    "Periodo": f'P{m["periodo"]}',
                    "Consumo Reactiva (kWh)": float(m["consumo"].replace('.', '').replace(',', '.')),
                    "Cos φ": float(m["cosphi"].replace(',', '.')),
                    "A facturar Reactiva (€)": float(m["a_facturar"].replace('.', '').replace(',', '.')),
                })

        st.success(f"✅ Energía reactiva inductiva extraída correctamente de {nombre_archivo}")
        return pd.DataFrame(datos)

    except Exception as e:
        st.error(f"Error al procesar Energía Reactiva Inductiva en {nombre_archivo}: {e}")
        return pd.DataFrame(columns=[
            "Archivo", "Periodo desde", "Periodo hasta", "Periodo",
            "Consumo Reactiva (kWh)", "Cos φ", "A facturar Reactiva (€)"
        ])


# ---------------------- EXCESOS DE POTENCIA ----------------------
def extraer_excesos_potencia(texto, periodo_desde, periodo_hasta, nombre_archivo):
    inicio = texto.find("EXCESOS DE POTENCIA")
    if inicio == -1:
        st.warning(f"❌ No se encontró Excesos de Potencia en {nombre_archivo}")
        return pd.DataFrame(columns=[
            "Archivo", "Periodo desde", "Periodo hasta", "Periodo",
            "Contratada (kW)", "Demandada (kW)", "A facturar Exceso (€)"
        ])

    bloque = _recortar_hasta_siguiente_cabecera(texto[inicio:])
    lineas = re.findall(r"P[1-6].+", bloque)
    datos = []

    if lineas:
        st.write(f"✅ Excesos de potencia encontrados en {nombre_archivo}")
        for linea in lineas:
            m = re.match(
                r"P(?P<periodo>[1-6])\s+"
                r"(?P<contratada>[\d.,]+)\s+"
                r"(?P<demandada>[\d.,]+)\s+"
                r"(?P<a_facturar>[\d.,]+)",
                linea
            )
            if m:
                datos.append({
                    "Archivo": nombre_archivo,
                    "Periodo desde": periodo_desde,
                    "Periodo hasta": periodo_hasta,
                    "Periodo": f'P{m["periodo"]}',
                    "Contratada (kW)": float(m["contratada"].replace('.', '').replace(',', '.')),
                    "Demandada (kW)": float(m["demandada"].replace('.', '').replace(',', '.')),
                    "A facturar Exceso (€)": float(m["a_facturar"].replace('.', '').replace(',', '.')),
                })
    else:
        st.warning(f"❌ No se reconocieron filas de Excesos en {nombre_archivo}")

    if not datos:
        return pd.DataFrame(columns=[
            "Archivo", "Periodo desde", "Periodo hasta", "Periodo",
            "Contratada (kW)", "Demandada (kW)", "A facturar Exceso (€)"
        ])
    return pd.DataFrame(datos)


# ---------------------- EXPORTAR A EXCEL ----------------------
def _ordenar_por_fecha(df: pd.DataFrame):
    """Convierte y ordena si la columna existe y el DF no está vacío."""
    if not df.empty and "Periodo desde" in df.columns:
        df["Periodo desde"] = pd.to_datetime(df["Periodo desde"], dayfirst=True, errors="coerce")
        df.sort_values("Periodo desde", inplace=True)

def generar_excel_acumulado(df_resumenes, df_activa, df_reactiva, df_excesos):
    for df in (df_resumenes, df_activa, df_reactiva, df_excesos):
        _ordenar_por_fecha(df)

    # Reconvertimos fechas a string dd/mm/yyyy
    for df in (df_resumenes, df_activa, df_reactiva, df_excesos):
        if not df.empty and "Periodo desde" in df.columns:
            df["Periodo desde"] = df["Periodo desde"].dt.strftime("%d/%m/%Y")

    total_kwh = df_activa.groupby("Archivo")["Consumo (kWh)"].sum().reset_index()
    total_kwh.rename(columns={"Consumo (kWh)": "Total Consumo (kWh)"}, inplace=True)

    total_reactiva = (df_reactiva.groupby("Archivo")["A facturar Reactiva (€)"].sum()
                      .reset_index()) if not df_reactiva.empty else pd.DataFrame(columns=["Archivo", "Total Reactiva Inductiva (€)"])
    total_reactiva.rename(columns={"A facturar Reactiva (€)": "Total Reactiva Inductiva (€)"}, inplace=True)

    total_excesos = (df_excesos.groupby("Archivo")["A facturar Exceso (€)"].sum()
                     .reset_index()) if not df_excesos.empty else pd.DataFrame(columns=["Archivo", "Total Excesos Potencia (€)"])
    total_excesos.rename(columns={"A facturar Exceso (€)": "Total Excesos Potencia (€)"}, inplace=True)

    df_totales = total_kwh.merge(total_reactiva, on="Archivo", how="outer").merge(total_excesos, on="Archivo", how="outer").fillna(0)

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

        activas.append(extraer_energia_activa(texto, periodo_desde, periodo_hasta, nombre_archivo))
        reactivas.append(extraer_reactiva_inducida(texto, periodo_desde, periodo_hasta, nombre_archivo))
        excesos.append(extraer_excesos_potencia(texto, periodo_desde, periodo_hasta, nombre_archivo))

    df_resumenes = pd.concat(resumenes, ignore_index=True)
    df_activas   = pd.concat(activas,   ignore_index=True)
    df_reactivas = pd.concat(reactivas, ignore_index=True)
    df_excesos   = pd.concat(excesos,   ignore_index=True)

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
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
