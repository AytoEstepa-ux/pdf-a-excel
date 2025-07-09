import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import re
import io
from pdf2image import convert_from_bytes
import pytesseract
from PIL import Image

st.set_page_config(page_title="Factura Alternativa a Excel", layout="centered")
st.title("📄 Convertidor PDF → Excel: Factura Endesa Alternativa")

uploaded_files = st.file_uploader("Sube tus facturas en PDF", type=["pdf"], accept_multiple_files=True)

# -------------------- FUNCIONES OCR --------------------

def aplicar_ocr_a_pdf(pdf_bytes):
    texto_ocr = ""
    poppler_bin_path = r"C:\Users\Maria\Documents\poppler-24.08.0\Library\bin"  # Ajusta si cambia
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

def extraer_datos_factura_alternativa(texto):
    campos = {
        "Factura nº": r"Nº de factura:\s*([A-Z0-9]+)",
        "Fecha Factura": r"Fecha emisión factura:\s*(\d{2}/\d{2}/\d{4})",
        "Fecha Límite de Pago": r"Fecha límite de pago:\s*(\d{2}\s+de\s+\w+\s+de\s+\d{4})",
        "Periodo Facturación": r"Periodo de facturación:\s*del\s*(\d{2}/\d{2}/\d{4})\s+al\s+(\d{2}/\d{2}/\d{4})",
        "Total Factura": r"IMPORTE FACTURA:\s*([\d.,]+)\s*€",
        "Cliente": r"Cliente\s+([A-ZÁÉÍÓÚÑ .,\d]+)",
        "Dirección Suministro": r"Dirección de suministro:\s*(.+?)\s*,\s*\d{5}\s*[A-Z]+",
        "CUPS": r"CUPS:\s*([A-Z\d]+)",
        "Contrato Nº": r"Referencia del contrato:\s*(\d+)",
        "Modalidad de Contrato": r"Contrato de mercado libre:\s*(.+)",
        "NIF/CIF": r"NIF:\s*([A-Z0-9]+)"
    }

    resultados = {}
    for campo, patron in campos.items():
        match = re.search(patron, texto)
        resultados[campo] = match.group(1).strip() if match else ""

    # Fechas de facturación
    match = re.search(campos["Periodo Facturación"], texto)
    if match:
        resultados["Inicio Facturación"] = match.group(1)
        resultados["Fin Facturación"] = match.group(2)
        resultados.pop("Periodo Facturación", None)

    return resultados

def extraer_detalle_consumo_y_potencia(texto):
    consumos = re.findall(r"Consumo P(\d)\s+([\d.,]+)\s*kWh\s+x\s*([\d.,]+)\s*Eur/kWh\s+([\d.,]+)\s*€", texto)
    potencias = re.findall(r"Pot\. P(\d)\s+([\d.,]+)\s*kW.*?([\d.,]+)\s*Eur/kW.*?([\d.,]+)\s*€", texto)

    data = []

    for p, kwh, precio, importe in consumos:
        data.append({
            "Periodo": f"P{p}",
            "Consumo kWh": float(kwh.replace('.', '').replace(',', '.')),
            "Precio kWh (€)": float(precio.replace('.', '').replace(',', '.')),
            "Importe Energía (€)": float(importe.replace('.', '').replace(',', '.'))
        })

    for p, kw, precio_kw, importe_kw in potencias:
        fila = next((f for f in data if f["Periodo"] == f"P{p}"), None)
        if fila:
            fila["Potencia Contratada (kW)"] = float(kw.replace('.', '').replace(',', '.'))
            fila["Precio kW (€)"] = float(precio_kw.replace('.', '').replace(',', '.'))
            fila["Importe Potencia (€)"] = float(importe_kw.replace('.', '').replace(',', '.'))

    return pd.DataFrame(data)

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

        resumen_dict = extraer_datos_factura_alternativa(texto)
        df_resumen = pd.DataFrame([resumen_dict])
        df_resumen['Archivo'] = uploaded_file.name

        # Convertir fechas
        df_resumen["Inicio Facturación"] = pd.to_datetime(df_resumen["Inicio Facturación"], dayfirst=True, errors='coerce')
        df_resumen["Fin Facturación"] = pd.to_datetime(df_resumen["Fin Facturación"], dayfirst=True, errors='coerce')

        df_detalle = extraer_detalle_consumo_y_potencia(texto)
        df_detalle['Archivo'] = uploaded_file.name
        df_detalle["Inicio Facturación"] = df_resumen["Inicio Facturación"].iloc[0]
        df_detalle["Fin Facturación"] = df_resumen["Fin Facturación"].iloc[0]

        df_resumen_total = pd.concat([df_resumen_total, df_resumen], ignore_index=True)
        df_detalle_total = pd.concat([df_detalle_total, df_detalle], ignore_index=True)

    # Reordenar y ordenar por fechas
    resumen_cols = ["Inicio Facturación", "Fin Facturación"] + [col for col in df_resumen_total.columns if col not in ["Inicio Facturación", "Fin Facturación"]]
    df_resumen_total = df_resumen_total[resumen_cols]

    detalle_cols = ["Inicio Facturación", "Fin Facturación"] + [col for col in df_detalle_total.columns if col not in ["Inicio Facturación", "Fin Facturación"]]
    df_detalle_total = df_detalle_total[detalle_cols]

    df_resumen_total.sort_values("Inicio Facturación", inplace=True)
    df_detalle_total.sort_values("Inicio Facturación", inplace=True)

    # Calcular totales
    total_kwh = df_detalle_total["Consumo kWh"].sum()
    total_importe_energia = df_detalle_total["Importe Energía (€)"].sum()
    total_importe_potencia = df_detalle_total["Importe Potencia (€)"].sum()

    # Mostrar resultados
    st.subheader("📋 Resumen de Facturas")
    st.dataframe(df_resumen_total)

    st.subheader("📊 Detalle de Consumo y Potencia")
    st.dataframe(df_detalle_total)

    st.markdown("### 🔢 Totales")
    st.write(f"**Total Consumo (kWh):** {total_kwh:,.2f} kWh")
    st.write(f"**Total Importe Energía (€):** {total_importe_energia:,.2f} €")
    st.write(f"**Total Importe Potencia (€):** {total_importe_potencia:,.2f} €")

    # Exportar a Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_resumen_total.to_excel(writer, sheet_name="Resumen", index=False)
        df_detalle_total.to_excel(writer, sheet_name="Detalle", index=False)

        workbook = writer.book
        worksheet = writer.sheets["Detalle"]
        bold = workbook.add_format({'bold': True})
        number = workbook.add_format({'num_format': '#,##0.00'})
        date_fmt = workbook.add_format({'num_format': 'dd/mm/yyyy'})

        # Formato fechas
        idx_ini = df_detalle_total.columns.get_loc("Inicio Facturación")
        idx_fin = df_detalle_total.columns.get_loc("Fin Facturación")
        worksheet.set_column(idx_ini, idx_ini, 15, date_fmt)
        worksheet.set_column(idx_fin, idx_fin, 15, date_fmt)

        # Formato números
        for i, col in enumerate(df_detalle_total.columns):
            if col not in ["Inicio Facturación", "Fin Facturación", "Periodo", "Archivo"]:
                worksheet.set_column(i, i, 15, number)

        # Totales
        startrow = len(df_detalle_total) + 2
        col_offset = 2
        worksheet.write(startrow - 1, col_offset + 1, "Consumo", bold)
        worksheet.write(startrow - 1, col_offset + 2, "Importe Energía", bold)
        worksheet.write(startrow - 1, col_offset + 3, "Importe Potencia", bold)

        worksheet.write(startrow, col_offset + 0, "TOTAL", bold)
        worksheet.write_number(startrow, col_offset + 1, total_kwh, number)
        worksheet.write_number(startrow, col_offset + 2, total_importe_energia, number)
        worksheet.write_number(startrow, col_offset + 3, total_importe_potencia, number)

    output.seek(0)

    st.download_button(
        label="⬇️ Descargar Excel",
        data=output,
        file_name="facturas_endesa_alternativas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
