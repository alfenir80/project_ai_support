
import os
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any

#importaçoes do RAG
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

#impotaçoes do LangChain
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain
from langchain_core.runnables import RunnablePassthrough
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.chat_history import BaseMessage, AIMessage, HumanMessage

from fastapi.middleware.cors import CORSMiddleware

# Carregar variáveis de ambiente
load_dotenv()

# Verificar se a chave da API do OpenAI está configurada
assert os.getenv("OPENAI_API_KEY") is not None, "OPENAI_API_KEY deve ser configurada no seu arquivo .env"

# --- Configuração da base de conhecimento RAG---

# Carregar documentos
loader = TextLoader('docs/produtos.txt', encoding='utf-8')

documents = loader.load()
# Dividir documentos em pedaços menores
text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
splits = text_splitter.split_documents(documents)

# Criar embeddings
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
# Criar vetor de armazenamento
vectorstore = Chroma.from_documents(splits, embeddings, collection_name="produtos")
# Criar cadeia de recuperação
retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 3})



# --- Ferramenta para o Agente ---
@tool
def get_product_info(query: str) -> Dict[str, Any]:
    """
    Ferramenta para buscar informações sobre produtos na base de conhecimento.
    """
    # Criar cadeia de recuperação
    retriever_docs = retriever.invoke(query)

   #formatar os documentos recuperados
    formatted_docs = "\n".join([doc.page_content for doc in retriever_docs])
    return {"status": "success", "docs": formatted_docs}

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

store = {}

def get_chat_history(user_id: str) -> BaseMessage:
    if user_id not in store:
        store[user_id] = []
    return store[user_id]

with_history = RunnableWithMessageHistory(
    agent_executor,
    get_chat_history,
    input_messages_key="input",
    history_messages_key="chat_history",
    return_messages=True,
)


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
    response = await agent_executor.ainvoke({"input": query.input},
                                            config = {"configurable" : {"user_id": "foo"}})
    
    return {"response": response['output']}