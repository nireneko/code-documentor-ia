import asyncio
import sqlite3
import uuid
import httpx
import zipfile
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query, status
import asyncio
from app.agent import graph 
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Configuración inicial
BASE_DIR = Path(__file__).resolve().parent.parent
FILES_DIR = BASE_DIR / "files"
UNZIP_DIR = FILES_DIR / "unzip"
DB_PATH = BASE_DIR / "database.db"

@app.on_event("startup")
def startup():
    # Crear directorios necesarios
    FILES_DIR.mkdir(exist_ok=True)
    UNZIP_DIR.mkdir(exist_ok=True)
    
    # Crear tabla en la base de datos
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analyses (
            uuid TEXT PRIMARY KEY,
            fecha INTEGER,
            analizado BOOLEAN
        )
    ''')
    conn.commit()
    conn.close()

def save_to_database(uuid_str: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO analyses (uuid, fecha, analizado) VALUES (?, ?, ?)",
            (uuid_str, int(datetime.now().timestamp()), False)
        )
        conn.commit()
    finally:
        conn.close()

async def download_file(url: str) -> bytes:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            
            # Verificar tipo de contenido
            content_type = response.headers.get('content-type', '')
            if 'zip' not in content_type:
                raise ValueError("El archivo no es un ZIP válido")
                
            return response.content
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=400, detail=f"Error al descargar el archivo: {str(e)}")

def unzip_file(zip_path: Path, dest_dir: Path):
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(dest_dir)
    except zipfile.BadZipFile:
        # Limpiar archivos en caso de error
        zip_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Archivo ZIP corrupto o inválido")

@app.get("/analyze")
async def analyze(file: str = Query(..., description="URL del archivo ZIP a analizar")):
    # Generar UUID único
    uuid_str = str(uuid.uuid4())
    
    # Descargar archivo
    try:
        file_content = await download_file(file)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Guardar ZIP
    zip_path = FILES_DIR / f"{uuid_str}.zip"
    zip_path.write_bytes(file_content)
    
    # Descomprimir
    dest_dir = UNZIP_DIR / uuid_str
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    # Ejecutar descompresión en un hilo separado
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, unzip_file, zip_path, dest_dir)
    
    # Guardar en base de datos
    await loop.run_in_executor(None, save_to_database, uuid_str)
    
    return {
        "status": "success",
        "uuid": uuid_str,
        "zip_path": str(zip_path),
        "unzip_dir": str(dest_dir)
    } # Asegúrate de que la importación sea correcta

@app.get("/analyze/{uuid}")
async def analyze_uuid(uuid: str):
    # Verificar si el UUID existe en la base de datos
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT analizado FROM analyses WHERE uuid = ?", (uuid,))
    result = cursor.fetchone()
    
    if not result:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="UUID no encontrado"
        )
    
    # Verificar si ya fue analizado
    #if result[0]:
    #    conn.close()
    #    return {"status": "already analyzed", "uuid": uuid}
    
    # Obtener ruta de los archivos descomprimidos
    unzip_path = UNZIP_DIR / uuid
    if not unzip_path.exists():
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archivos no encontrados para el UUID"
        )
    
    # Procesar archivos con LangGraph
    try:
        # Crear estado inicial para LangGraph
        initial_state = {
            "unzip_path": str(unzip_path),
            "file": "",
            "code": "",
            "contents": [],
            "analysis": [],
            "final_documentation": ""
        }

        result = graph.invoke(initial_state)

        print(result)

        # Actualizar base de datos
        cursor.execute(
            "UPDATE analyses SET analizado = ? WHERE uuid = ?",
            (True, uuid)
        )
        # conn.commit()
        
        return {
            "uuid": uuid,
            "status": "analyzed",
            "documentation-overview": result.get("analysis", "")
        }
        
    except Exception as e:
        # Revertir cambios en caso de error
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en el análisis: {str(e)}"
        )
    finally:
        conn.close()