
import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Dict, Any

import fitz

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

model = ChatOpenAI(model="gpt-4o", temperature=0)
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

user_vectorstores_and_retrievers: Dict[str, Any] = {}

# --- Ferramenta para o Agente ---
#Armazenamento de histórico de conversa em Redis
def get_chat_history(session_id: str) -> RedisChatMessageHistory:
    return RedisChatMessageHistory(session_id, url="redis://localhost:6379/0")

def get_or_create_rag_components(session_id: str) -> Dict[str, Any]:
    """
    Função para criar ou obter componentes RAG.
    """
    if session_id not in user_vectorstores_and_retrievers:
        # Criar um novo vetor e recuperador para o usuário
        vectorstore = Chroma(embedding_function=embeddings, collection_name=f"user_doc_{session_id}")   
        retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 3})
        user_vectorstores_and_retrievers[session_id] = {
            "vectorstore": vectorstore,
            "retriever": retriever
        }
    return user_vectorstores_and_retrievers[session_id]
    

@tool
def search_document_knowledge_base(query: str, session_id: str) -> str:
    """
    Ferramenta para buscar na base de conhecimento do usuário.
    """
    if session_id not in user_vectorstores_and_retrievers:
        return "Nenhum documento foi carregado. Por favor, carregue um documento primeiro."
    
    retriever = user_vectorstores_and_retrievers[session_id]["retriever"]
    retriever_docs = retriever.invoke(query)
    formatted_docs = "\n".join([doc.page_content for doc in retriever_docs])
    return formatted_docs if formatted_docs else "Nenhum documento relevante encontrado."   


tools = [search_document_knowledge_base]

prompt= ChatPromptTemplate.from_messages([
    ("system", """
    Você é um assistente de suporte ao cliente. Seu objetivo é responder perguntas com base no DOCUMENTO que o usuário enviou.
    Se a pergunta for sobre o conteúdo do documento, use a ferramenta 'search_document_knowledge' para encontrar a informação.
    Se a pergunta não puder ser respondida com base no documento, diga que você não tem essa informação ou peça para o usuário esclarecer.
    Não responda perguntas gerais que não estejam relacionadas ao documento.ssistente útil que ajuda os usuários a responder perguntas com base em documentos que eles carregaram.
    Use as ferramentas disponíveis para buscar informações relevantes. Se a informação não estiver disponível, responda honestamente que você não sabe.
     """),
    ("placeholder", "{chat_history}"),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}")
])

agent = create_tool_calling_agent(model, tools, prompt)
agent_executor = AgentExecutor.from_agent_and_tools(agent=agent, tools=tools, verbose=True)

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

class UploadResponse(BaseModel):
    status: str
    message: str



@app.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...), session_id: str = "default_session"):
    """
    Endpoint para upload de arquivos PDF.
    """
    
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF são suportados.")
    try:
        # Ler o conteúdo do arquivo PDF
        pdf_content = await file.read()
        pdf_document = fitz.open(stream=pdf_content, filetype="pdf")
        text = ""
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            text += page.get_text()
        pdf_document.close()
        
        if not text.strip():
            raise HTTPException(status_code=400, detail="O arquivo PDF está vazio ou não contém texto extraível.")  
        
        # Dividir o texto em chunks
        chunks = text_splitter.create_documents([text])
        
        if session_id in user_vectorstores_and_retrievers:
            # Limpar a coleção existente para o usuário
            user_vectorstores_and_retrievers[session_id]["vectorstore"].delete_collection()
            del user_vectorstores_and_retrievers[session_id]
            print(f"Limpeza da coleção existente para a sessão {session_id}.")
        
        vectorstore = Chroma.from_documents(chunks, embeddings, collection_name=f"user_doc_{session_id}")
        retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 3})
        user_vectorstores_and_retrievers[session_id] = {
            "vectorstore": vectorstore,
            "retriever": retriever
        }
        return UploadResponse(status="success", message="Arquivo carregado e processado com sucesso.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar o arquivo: {str(e)}")   
    
    
        
           


@app.post("/query", response_model=Dict[str, str])
async def query_agent(query: Query):
    """
    Endpoint para enviar perguntas ao agente.
    """
    if query.session_id not in user_vectorstores_and_retrievers:
        return {"response": "Nenhum documento foi carregado. Por favor, carregue um documento primeiro."}
    
    response =await with_history.invoke({"input": query.input, "session_id": query.session_id})
    return {"response": response.content}

