from typing import TypedDict, Annotated
from langchain_openai import ChatOpenAI
from langgraph.graph import START, END, StateGraph
from langgraph.constants import Send
from pathlib import Path
from pydantic import BaseModel, Field
import operator
from dotenv import load_dotenv

load_dotenv()

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

class State(TypedDict):
    unzip_path: str
    contents: list[dict]
    analysis: Annotated[list, operator.add]
    code: str
    file: str
    final_documentation: str

class CodeDoc(BaseModel):
    """Documentation of the given code"""
    markdown: str = Field(description="Markdown documentation")

# Ruta a la carpeta 'code' en la raíz del proyecto
code_analysis_prompt = "Take time to analyze and understand the given code, generate documentation explainig what functions or methods does, dont describe parameters, arguments or return. Response only markdown: {code}"
code_documentation_prompt = "Take your time to read and understand the markdown that comes from the documentation of a Drupal 10 module, generate documentation describing what is todes. Response only markdown: {text}"

def read_directory_recursive(directory: Path):
    contenidos = []
    for element in directory.rglob('*'):
        # Ignorar archivos dentro de la carpeta "tests"
        if "tests" in element.parts:
            continue
        if element.is_file() and element.suffix == '.php':
            try:
                # Lee el contenido del archivo (asumiendo que es de texto y en UTF-8)
                contenido = element.read_text(encoding='utf-8')
                # Agrega un diccionario con la ruta (del directorio), el nombre y el contenido a la lista
                contenidos.append({
                    'ruta': str(element.parent),  # Directorio donde se encuentra el archivo
                    'nombre': element.name,       # Nombre del archivo
                    'content': contenido
                })
            except Exception as e:
                print(f"Error al leer {element}: {e}")
    return contenidos

# Node 1
def node_read_file_contents(state: State) -> State:
    state["contents"] = read_directory_recursive(Path(state["unzip_path"]))
    return state

# Node 2
def node_llm_request_for_analysis(state: State) -> State:
    prompt = code_analysis_prompt.format(code=state["code"])
    # Generamos una predicción estructurada del sentimiento del tweet
    # Referencia: https://python.langchain.com/docs/how_to/structured_output/
    response = llm.with_structured_output(CodeDoc).invoke(prompt)
    return {"analysis": [response.markdown], }

def node_generate_documentation(state: State) -> State:
    prompt = code_documentation_prompt.format(text=''.join(state['analysis']))
    response = llm.with_structured_output(CodeDoc).invoke(prompt)
    return {"analysis": [response.markdown], }

def edge_prepare_code_send(state: State):
    return [Send("node_llm_request_for_analysis", {"code": data["content"], 'file': data["ruta"] + "/" + data["nombre"]}) for data in state["contents"]]


builder = StateGraph(State)

builder.add_node("node_read_file_contents", node_read_file_contents)
builder.add_node("node_llm_request_for_analysis", node_llm_request_for_analysis)
builder.add_node("node_generate_documentation", node_generate_documentation)

builder.add_edge(START, "node_read_file_contents")
builder.add_conditional_edges("node_read_file_contents", edge_prepare_code_send, ["node_llm_request_for_analysis"])
builder.add_edge("node_llm_request_for_analysis", "node_generate_documentation")
builder.add_edge("node_generate_documentation", END)

graph = builder.compile()