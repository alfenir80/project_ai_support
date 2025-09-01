
import os
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any

# Importações para o RAG
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

# Importações do LangChain e Memória com Redis
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.chat_history import BaseMessage, AIMessage, HumanMessage

import redis
from langchain_community.chat_message_histories import RedisChatMessageHistory
# Importação para CORS
from fastapi.middleware.cors import CORSMiddleware

# Carregar variáveis de ambiente
load_dotenv()
assert os.getenv("OPENAI_API_KEY") is not None, "OPENAI_API_KEY deve ser configurada no seu arquivo .env"

# --- Configuração da base de conhecimento RAG ---
loader = TextLoader('docs/produtos.txt', encoding='utf-8')
documents = loader.load()
text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
splits = text_splitter.split_documents(documents)
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = Chroma.from_documents(splits, embeddings, collection_name="produtos")
retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 3})

# --- Ferramenta para o Agente ---
@tool
def search_knowledge_base(query: str) -> str:
    """
    Use esta ferramenta para pesquisar informações em nossa base de dados.
    Entrada deve ser a pergunta do usuário ou a informação que ele busca.
    """
    retrieved_docs = retriever.invoke(query)
    # Formatar os documentos para que o agente possa usar o texto diretamente
    formatted_docs = "\n".join([doc.page_content for doc in retrieved_docs])
    return formatted_docs

# --- Configuração do Agente LangChain e Memória com Redis ---
model = ChatOpenAI(model="gpt-4o", temperature=0)
tools = [search_knowledge_base] # Usar a ferramenta corrigida

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "Você é um assistente de suporte ao cliente. Responda perguntas sobre produtos e políticas da loja. Use a sua ferramenta de busca para obter as informações necessárias."),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ]
)

agent = create_tool_calling_agent(model, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# Armazenamento de histórico de conversa em Redis
def get_chat_history(session_id: str) -> RedisChatMessageHistory:
    return RedisChatMessageHistory(session_id, url="redis://localhost:6379/0")

# Envolver o agente com a funcionalidade de histórico
with_history = RunnableWithMessageHistory(
    agent_executor,
    get_chat_history,
    input_messages_key="input",
    history_messages_key="chat_history",
)

# --- Configuração da API FastAPI ---
app = FastAPI()

origins = ["http://localhost", "http://localhost:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Query(BaseModel):
    input: str
    session_id: str

@app.post("/query")
async def query_agent(query: Query):
    """
    Endpoint para consultar o agente com uma pergunta.
    """
    # A chamada agora usa o objeto 'with_history' e o 'session_id' da requisição
    response = await with_history.ainvoke(
        {"input": query.input},
        config={"configurable": {"session_id": query.session_id}}
    )
    return {"response": response['output']}