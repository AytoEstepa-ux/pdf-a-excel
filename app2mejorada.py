import streamlit as st  
import pandas as pd
import fitz  # PyMuPDF
import re
import io
from pdf2image import convert_from_bytes
import pytesseract
from PIL import Image

st.set_page_config(page_title="Factura Endesa a Excel", layout="centered")
st.title("📄 Convertidor PDF → Excel: Factura Endesa")

uploaded_files = st.file_uploader("Sube tus facturas en PDF", type=["pdf"], accept_multiple_files=True)

# -------------------- FUNCIONES OCR --------------------

def aplicar_ocr_a_pdf(pdf_bytes):
    texto_ocr = ""
    poppler_bin_path = r"C:\Users\Maria\Documents\poppler-24.08.0\Library\bin"
    try:
        imagenes = convert_from_bytes(pdf_bytes, poppler_path=poppler_bin_path)
        for img in imagenes:
            texto_ocr += pytesseract.image_to_string(img, lang='spa') + "\n"
    except Exception as e:
        st.warning(f"OCR falló: {e}")
    return texto_ocr

def obtener_texto_pdf(uploaded_file):
    pdf_bytes = uploaded_file.read()
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        texto = ""
        for page in doc:
            texto += page.get_text()
    if len(texto.strip()) < 100:
        st.info(f"🧐 Detectado PDF escaneado: {uploaded_file.name}. Aplicando OCR...")
        texto = aplicar_ocr_a_pdf(pdf_bytes)
    return texto

# -------------------- FUNCIONES DE EXTRACCIÓN --------------------

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
    patron = re.compile(
        r"Periodo\s+([1-6])(?:\s+Capacitiva)?\s+" +
        r"([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+" +
        r"([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+" +
        r"([\d.,]+)"
    )
    filas = []
    for match in patron.finditer(texto):
        valores = [match.group(i).replace('.', '').replace(',', '.') for i in range(1, 13)]
        fila = {
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

# -------------------- PROCESAMIENTO PRINCIPAL --------------------

df_resumen_total = pd.DataFrame()
df_detalle_total = pd.DataFrame()

if uploaded_files:
    for uploaded_file in uploaded_files:
        texto = obtener_texto_pdf(uploaded_file)

        if not texto.strip():
            st.warning(f"❌ No se pudo extraer texto del archivo: {uploaded_file.name}")
            continue

        st.success(f"✅ PDF procesado correctamente: {uploaded_file.name}")

        resumen_dict = extraer_datos_generales(texto)
        df_resumen = pd.DataFrame([resumen_dict])
        df_resumen['Archivo'] = uploaded_file.name

        # Extraer fechas desde "Periodo Facturación"
        df_resumen[["Inicio Facturación", "Fin Facturación"]] = df_resumen["Periodo Facturación"].str.extract(
            r"(\d{2}/\d{2}/\d{4})\s+al\s+(\d{2}/\d{2}/\d{4})"
        )
        df_resumen["Inicio Facturación"] = pd.to_datetime(df_resumen["Inicio Facturación"], dayfirst=True, errors='coerce')
        df_resumen["Fin Facturación"] = pd.to_datetime(df_resumen["Fin Facturación"], dayfirst=True, errors='coerce')

        # Eliminar columna original
        df_resumen.drop(columns=["Periodo Facturación"], inplace=True)

        periodo_facturacion = resumen_dict.get("Periodo Facturación", "")
        df_detalle = extraer_tabla_energia_y_potencia(texto, periodo_facturacion)
        df_detalle['Archivo'] = uploaded_file.name

        # Extraer fechas también al detalle
        match = re.search(r"(\d{2}/\d{2}/\d{4})\s+al\s+(\d{2}/\d{2}/\d{4})", periodo_facturacion)
        if match:
            inicio = pd.to_datetime(match.group(1), dayfirst=True, errors='coerce')
            fin = pd.to_datetime(match.group(2), dayfirst=True, errors='coerce')
            df_detalle["Inicio Facturación"] = inicio
            df_detalle["Fin Facturación"] = fin

        df_resumen_total = pd.concat([df_resumen_total, df_resumen], ignore_index=True)
        df_detalle_total = pd.concat([df_detalle_total, df_detalle], ignore_index=True)

    # Reordenar columnas para que Inicio y Fin estén primero
    resumen_cols = ["Inicio Facturación", "Fin Facturación"] + [col for col in df_resumen_total.columns if col not in ["Inicio Facturación", "Fin Facturación"]]
    df_resumen_total = df_resumen_total[resumen_cols]

    detalle_cols = ["Inicio Facturación", "Fin Facturación"] + [col for col in df_detalle_total.columns if col not in ["Inicio Facturación", "Fin Facturación"]]
    df_detalle_total = df_detalle_total[detalle_cols]

    # Ordenar por Inicio de Facturación
    df_resumen_total.sort_values("Inicio Facturación", inplace=True)
    df_detalle_total.sort_values("Inicio Facturación", inplace=True)

    # Calcular totales
    total_consumo_kwh = df_detalle_total["Consumo kWh"].sum()
    total_importe_reactiva = df_detalle_total["Importe Reactiva (€)"].sum()
    total_importe_potencia = df_detalle_total["Importe Potencia (€)"].sum()

    # Mostrar resultados
    st.subheader("📋 Resumen de las Facturas")
    st.dataframe(df_resumen_total)

    st.subheader("📊 Energía y Potencia por Periodo")
    st.dataframe(df_detalle_total)

    st.markdown("### 🔢 Totales")
    st.write(f"**Total Consumo (kWh):** {total_consumo_kwh:,.2f} kWh")
    st.write(f"**Total Importe Energía Reactiva (€):** {total_importe_reactiva:,.2f} €")
    st.write(f"**Total Importe Potencia (€):** {total_importe_potencia:,.2f} €")

    # Crear archivo Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_resumen_total.to_excel(writer, sheet_name="Resumen Facturas", index=False)
        df_detalle_total.to_excel(writer, sheet_name="Energía y Potencia", index=False)

        workbook = writer.book
        worksheet_detalle = writer.sheets["Energía y Potencia"]

        # Formatos
        date_format = workbook.add_format({'num_format': 'dd/mm/yyyy'})
        number_format = workbook.add_format({'num_format': '#,##0.00'})
        bold_format = workbook.add_format({'bold': True})

        # Aplicar formato fecha a columnas Inicio y Fin Facturación
        for col_name in ["Inicio Facturación", "Fin Facturación"]:
            if col_name in detalle_cols:
                col_idx = detalle_cols.index(col_name)
                worksheet_detalle.set_column(col_idx, col_idx, 15, date_format)

        # Aplicar formato numérico a columnas numéricas
        for col_name in ["Consumo kWh", "Reactiva (kVArh)", "Exceso Reactiva", "Importe Reactiva (€)", "Potencia Contratada",
                         "Max. Registrada", "Kp", "Te", "Excesos Potencia", "Importe Potencia (€)"]:
            if col_name in detalle_cols:
                col_idx = detalle_cols.index(col_name)
                worksheet_detalle.set_column(col_idx, col_idx, 15, number_format)

        # Escribir fila total desplazada dos columnas a la derecha
        startrow = len(df_detalle_total) + 2
        col_offset = 2

        worksheet_detalle.write(startrow, col_offset + 0, "TOTAL", bold_format)  # Periodo
        worksheet_detalle.write_number(startrow, col_offset + 1, total_consumo_kwh, number_format)  # Consumo kWh
        worksheet_detalle.write_number(startrow, col_offset + 2, total_importe_reactiva, number_format)  # Importe Reactiva (€)
        worksheet_detalle.write_number(startrow, col_offset + 3, total_importe_potencia, number_format)  # Importe Potencia (€)

    output.seek(0)

    st.download_button(
        label="⬇️ Descargar Excel",
        data=output,
        file_name="facturas_endesa_acumuladas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
