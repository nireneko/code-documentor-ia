from typing import Union
from fastapi import FastAPI, HTTPException, Query
import aiohttp
import os
import zipfile
from urllib.parse import urlparse

app = FastAPI()

# Carpeta donde se guardarán los archivos
FILES_DIR = "files"
UNZIP_DIR = os.path.join(FILES_DIR, "unzipped")
os.makedirs(UNZIP_DIR, exist_ok=True)


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}

@app.get("/analyze")
async def analyze(file: str = Query(..., title="URL del archivo ZIP")):
    # Validar que la URL es de un archivo ZIP
    parsed_url = urlparse(file)
    if not parsed_url.scheme.startswith(("http", "https")) or not file.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Debe proporcionar una URL válida de un archivo ZIP.")

    # Obtener el nombre del archivo
    filename = os.path.basename(parsed_url.path)
    file_path = os.path.join(FILES_DIR, filename)

    # Descargar el archivo ZIP
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(file) as response:
                if response.status != 200:
                    raise HTTPException(status_code=400, detail="No se pudo descargar el archivo.")
                
                # Guardar el archivo en la carpeta "files"
                with open(file_path, "wb") as f:
                    f.write(await response.read())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al descargar el archivo: {str(e)}")

    # Carpeta de extracción
    extract_path = os.path.join(UNZIP_DIR, filename.replace(".zip", ""))
    os.makedirs(extract_path, exist_ok=True)

    # Descomprimir el archivo ZIP
    try:
        with zipfile.ZipFile(file_path, "r") as zip_ref:
            zip_ref.extractall(extract_path)
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="El archivo descargado no es un ZIP válido.")

    return {
        "message": "Archivo descargado y descomprimido correctamente",
        "filename": filename,
        "saved_path": file_path,
        "unzipped_path": extract_path
    }