if datos_periodo:
    # Crear DataFrame
    df = pd.DataFrame(datos_periodo)

    # Asegurar que los nombres de columnas sean únicos
    df.columns = [str(col).strip() for col in df.columns]

    # Convertir "Importe Potencia (€)" a numérico para sumar
    df["Importe Potencia (€)"] = df["Importe Potencia (€)"].str.replace('.', '', regex=False).str.replace(',', '.', regex=False).astype(float)
    total_potencia = df["Importe Potencia (€)"].sum()

    # Agregar columna de Periodo de Facturación (igual para todos los registros)
    df["Periodo de Facturación"] = periodo_facturacion if periodo_facturacion else ""

    # Fila de totales (incluye total de potencia y total factura general)
    fila_total = {
        "Periodo": "TOTAL",
        "Energía Activa (kWh)": "",
        "Energía Reactiva (kVArh)": "",
        "Potencia Contratada (kW)": "",
        "Potencia Máxima (kW)": "",
        "Importe Potencia (€)": total_potencia,
        "Periodo de Facturación": "TOTAL FACTURA: " + (total_factura if total_factura else "")
    }
    df = pd.concat([df, pd.DataFrame([fila_total])], ignore_index=True)

    # Mostrar DataFrame en Streamlit
    df_display = df.copy()
    df_display["Importe Potencia (€)"] = df_display["Importe Potencia (€)"].apply(
        lambda x: f"{x:,.2f}".replace(".", ",") if isinstance(x, float) else x
    )

    st.subheader("📊 Datos por periodo")
    st.dataframe(df_display)

    if periodo_facturacion:
        st.markdown(f"📆 **Periodo de facturación:** {periodo_facturacion}")
    if total_factura:
        st.markdown(f"🧾 **Total factura general:** {total_factura} €")

    # Exportar a Excel
    salida_excel = BytesIO()
    df_display.to_excel(salida_excel, index=False, engine='openpyxl')
    salida_excel.seek(0)

    st.download_button(
        label="⬇️ Descargar Excel",
        data=salida_excel,
        file_name="factura_periodos.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


