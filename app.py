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

def extraer_energia_potencia_comb(texto):
    datos = []
    lineas = texto.splitlines()

    i = 0
    while i < len(lineas):
        linea = lineas[i].strip()

        # Línea que empieza con 'Periodo' y contiene energía
        energia_match = re.match(
            r"Periodo\s+(\d).*?([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)", linea
        )

        if energia_match:
            p, act, react, exc_kvarh, cosphi, imp_energia = energia_match.groups()

            # Leer línea siguiente como potencia
            if i + 1 < len(lineas):
                linea_potencia = lineas[i + 1].strip()
                # Extraer todos los números con decimales o separadores
                partes = re.findall(r"[\d.,]+", linea_potencia)
                if len(partes) >= 4:
                    pot_contr, pot_max, exc_kw, imp_potencia = partes[:4]

                    datos.append({
                        "Periodo": f"P{p}",
                        "Energía Activa (kWh)": act,
                        "Energía Reactiva (kVArh)": react,
                        "Excesos (kVArh)": exc_kvarh,
                        "Cos φ": cosphi,
                        "Importe Energía (€)": imp_energia,
                        "Potencia Contratada (kW)": pot_contr,
                        "Potencia Máxima (kW)": pot_max,
                        "Excesos (kW)": exc_kw,
                        "Importe Excesos Potencia (€)": imp_potencia
                    })

                    i += 2
                    continue

        i += 1

    return datos

if archivo_pdf:
    texto = ""
    with pdfplumber.open(archivo_pdf) as pdf:
        for pagina in pdf.pages:
            texto += pagina.extract_text() + "\n"

    periodo_facturacion = extraer_periodo_facturacion(texto)
    total_factura = extraer_total_factura(texto)
    datos = extraer_energia_potencia_comb(texto)

    if datos:
        df = pd.DataFrame(datos)

        # Convertir columnas numéricas (monetarias) a float
        columnas_float = [
            "Importe Energía (€)",
            "Excesos (kVArh)",
            "Excesos (kW)",
            "Importe Excesos Potencia (€)"
        ]
        for col in columnas_float:
            df[col] = df[col].str.replace('.', '', regex=False).str.replace(',', '.', regex=False).astype(float)

        df["Periodo de Facturación"] = periodo_facturacion if periodo_facturacion else ""

        fila_total = {
            "Periodo": "TOTAL",
            "Energía Activa (kWh)": "",
            "Energía Reactiva (kVArh)": "",
            "Excesos (kVArh)": df["Excesos (kVArh)"].sum(),
            "Cos φ": "",
            "Importe Energía (€)": df["Importe Energía (€)"].sum(),
            "Potencia Contratada (kW)": "",
            "Potencia Máxima (kW)": "",
            "Excesos (kW)": df["Excesos (kW)"].sum(),
            "Importe Excesos Potencia (€)": df["Importe Excesos Potencia (€)"].sum(),
            "Periodo de Facturación": "TOTAL FACTURA: " + (total_factura if total_factura else "")
        }
        df = pd.concat([df, pd.DataFrame([fila_total])], ignore_index=True)

        # Formato visual
        df_display = df.copy()
        for col in ["Importe Energía (€)", "Importe Excesos Potencia (€)"]:
            df_display[col] = df_display[col].apply(
                lambda x: f"{x:,.2f}".replace(".", ",") if isinstance(x, float) else x
            )

        st.subheader("📊 Datos por periodo (energía y potencia)")
        st.dataframe(df_display)

        if periodo_facturacion:
            st.markdown(f"📆 **Periodo de facturación:** {periodo_facturacion}")
        if total_factura:
            st.markdown(f"🧾 **Total factura general:** {total_factura} €")

        salida_excel = BytesIO()
        df_display.to_excel(salida_excel, index=False, engine='openpyxl')
        salida_excel.seek(0)

        st.download_button(
            label="⬇️ Descargar Excel",
            data=salida_excel,
            file_name="factura_periodos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.error("❌ No se encontraron datos de energía y potencia en el PDF.")


