
import os
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any

from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool

from fastapi.middleware.cors import CORSMiddleware

# Carregar variáveis de ambiente
load_dotenv()

# Verificar se a chave da API do OpenAI está configurada
assert os.getenv("OPENAI_API_KEY") is not None, "OPENAI_API_KEY deve ser configurada no seu arquivo .env"

# --- Dados de Exemplo da Base de Conhecimento ---
db_produtos = {
    "telefone_modelo_a": {
        "nome": "Smartphone Modelo A",
        "preco": "R$ 1500",
        "especificacoes": "Tela 6.1, 128GB, câmera 48MP"
    },
    "fone_modelo_b": {
        "nome": "Fone de Ouvido Modelo B",
        "preco": "R$ 350",
        "especificacoes": "Cancelamento de ruído, bateria de 10h"
    },
    "politicas": {
        "garantia": "Garantia de 1 ano contra defeitos de fabricação.",
        "trocas": "Trocas podem ser solicitadas em até 30 dias após a compra."
    }
}

# --- Ferramenta para o Agente ---
@tool
def get_product_info(query: str) -> Dict[str, Any]:
    """
    Use esta ferramenta para obter informações sobre produtos ou políticas da loja.
    Entrada deve ser uma string clara com o nome do produto ou tipo de política (ex: "garantia", "telefone_modelo_a").
    """
    query_lower = query.lower().replace(" ", "_")
    
    info = db_produtos.get(query_lower)
    
    if info:
        return info
    else:
        return {"status": "não encontrado", "detalhes": f"Informação sobre '{query}' não encontrada na nossa base de dados."}

# --- Configuração do Agente LangChain (fora da função) ---
model = ChatOpenAI(model="gpt-4o", temperature=0)
tools = [get_product_info]

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "Você é um assistente de suporte ao cliente. Responda perguntas sobre produtos e políticas da loja. Use suas ferramentas para obter informações."),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ]
)

agent = create_tool_calling_agent(model, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# --- Configuração da API FastAPI ---
app = FastAPI()
#Configuração do CORS (opcional, se necessário)
# Configuração do CORS
origins = ["http://localhost", "http://localhost:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Definição do modelo de dados para a requisição de chat
class Query(BaseModel):
    input: str

@app.post("/query")
async def query_agent(query: Query):
    """
    Endpoint para consultar o agente com uma pergunta.
    """
    response = await agent_executor.ainvoke({"input": query.input})
    
    return {"response": response['output']}