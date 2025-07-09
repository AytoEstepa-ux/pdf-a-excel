from pdf2image import convert_from_bytes

# Cambia esta ruta por donde tengas el PDF para probar
archivo_pdf = r"C:\Users\Maria\Documents\factura-analyzer\F25100479 diez dias enero primera sustituida.pdf"

# Ruta donde descomprimiste Poppler (la carpeta 'bin')
poppler_bin_path = r"C:\Users\Maria\Documents\poppler-24.08.0\Library\bin"

try:
    with open(archivo_pdf, "rb") as f:
        pdf_bytes = f.read()

    # Aquí pasamos poppler_path sin modificar el PATH de Windows
    imagenes = convert_from_bytes(pdf_bytes, poppler_path=poppler_bin_path)

    print(f"Se generaron {len(imagenes)} imágenes del PDF")

except Exception as e:
    print(f"Error: {e}")
