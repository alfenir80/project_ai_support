import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import Dict, Any, List
import fitz  # PyMuPDF
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import RedisChatMessageHistory
from fastapi.middleware.cors import CORSMiddleware
import logging

# Configurar logging
logger = logging.getLogger(__name__)

# Carregar variáveis de ambiente
load_dotenv()

# Validar variáveis de ambiente críticas
REQUIRED_ENV_VARS = ["OPENAI_API_KEY"]
for var in REQUIRED_ENV_VARS:
    if not os.getenv(var):
        raise RuntimeError(f"{var} deve ser configurada no seu arquivo .env")

# Configurações
class Settings:
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))
    MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

settings = Settings()

# --- Configuração de Modelos e Ferramentas ---
model = ChatOpenAI(model=settings.MODEL_NAME, temperature=0)
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=settings.CHUNK_SIZE, 
    chunk_overlap=settings.CHUNK_OVERLAP
)
embeddings = OpenAIEmbeddings(model=settings.EMBEDDING_MODEL)

# Gerenciamento de vectorstores por sessão
user_vectorstores: Dict[str, Chroma] = {}

class SearchQuery(BaseModel):
    query: str = Field(description="A pergunta ou termo de busca para procurar no documento.")
    session_id: str = Field(description="O ID da sessão do usuário para encontrar o documento correto.")

# --- Gerenciamento de Memória (Chat History) ---
def get_chat_history(session_id: str) -> RedisChatMessageHistory:
    """Obter histórico de chat do Redis com tratamento de erro"""
    try:
        return RedisChatMessageHistory(session_id, url=settings.REDIS_URL)
    except Exception as e:
        logger.error(f"Erro ao conectar com Redis para sessão {session_id}: {e}")
        # Fallback: retornar histórico em memória se Redis falhar
        from langchain.memory import ChatMessageHistory
        return ChatMessageHistory()

# --- Ferramenta para o Agente --- CORRIGIDA
@tool
def search_document_knowledge_base(query: str, session_id: str) -> str:
    """
    Ferramenta para buscar na base de conhecimento do usuário com base no documento carregado.
    Use esta ferramenta quando precisar buscar informações específicas no documento carregado pelo usuário.
    
    Args:
        query: A pergunta ou termo de busca para procurar no documento
        session_id: O ID da sessão do usuário para encontrar o documento correto
    """
    logger.info(f"Consultando documento para sessão {session_id}: {query}")
    
    if session_id not in user_vectorstores:
        return "Nenhum documento foi carregado para esta sessão. Por favor, carregue um documento primeiro."
    
    try:
        retriever = user_vectorstores[session_id].as_retriever(
            search_type="similarity", 
            search_kwargs={"k": 3}
        )
        retrieved_docs = retriever.get_relevant_documents(query)
        
        if not retrieved_docs:
            return "Nenhum documento relevante encontrado para a sua pergunta."
        
        formatted_docs = "\n\n--- Documento Recuperado ---\n\n".join([doc.page_content for doc in retrieved_docs])
        return formatted_docs
    
    except Exception as e:
        logger.error(f"Erro ao buscar no vectorstore para sessão {session_id}: {e}")
        return "Ocorreu um erro interno ao buscar no documento. Tente novamente."

tools = [search_document_knowledge_base]

# --- Prompt do Agente --- ATUALIZADO
prompt = ChatPromptTemplate.from_messages([
    ("system", """
     Você é um assistente especializado em responder perguntas sobre documentos PDF carregados pelos usuários.

     INSTRUÇÕES IMPORTANTES:
     1. SEMPRE use a ferramenta 'search_document_knowledge_base' quando o usuário fizer uma pergunta sobre o conteúdo do documento.
     2. Passe dois parâmetros para a ferramenta:
        - query: a pergunta do usuário
        - session_id: o ID da sessão fornecido pelo usuário
     3. Baseie sua resposta estritamente nas informações retornadas pela ferramenta.
     4. Se a informação não for encontrada no documento, diga claramente que não encontrou a informação solicitada.
     5. Mantenha as respostas claras, objetivas e em português brasileiro.

     Exemplo de uso correto:
     Usuário: "Qual é o resumo executivo?"
     Você: Invocar a ferramenta com query="resumo executivo" e session_id="id_da_sessao"
     """),
    ("placeholder", "{chat_history}"),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}")
])

# Configurar o agente com melhor tratamento de erros
agent = create_tool_calling_agent(model, tools, prompt)
agent_executor = AgentExecutor.from_agent_and_tools(
    agent=agent, 
    tools=tools, 
    verbose=True,
    handle_parsing_errors=True,
    return_intermediate_steps=False
)

with_history = RunnableWithMessageHistory(
    agent_executor,
    get_chat_history,
    input_messages_key="input",
    history_messages_key="chat_history",
)

# --- Configuração da API FastAPI ---
app = FastAPI(title="Document Q&A API", version="1.0.0")

# Configuração CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Modelos Pydantic para Validação de Dados ---
class Query(BaseModel):
    input: str
    session_id: str

class UploadResponse(BaseModel):
    status: str
    message: str
    session_id: str
    pages_processed: int = 0

class QueryResponse(BaseModel):
    response: str
    session_id: str

# --- Endpoint para Health Check ---
@app.get("/")
async def health_check():
    return {"status": "healthy", "service": "Document Q&A API"}

# --- Endpoint para Upload de Documentos ---
@app.post("/upload_document", response_model=UploadResponse)
async def upload_document(session_id: str = Form(...), file: UploadFile = File(...)):
    """
    Faz upload e processa um documento PDF para uma sessão específica.
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF são suportados.")
    
    try:
        # Ler e validar o arquivo
        pdf_content = await file.read()
        if len(pdf_content) == 0:
            raise HTTPException(status_code=400, detail="O arquivo está vazio.")
        
        # Processar PDF
        pdf_document = fitz.open(stream=pdf_content, filetype="pdf")
        text = ""
        pages_processed = 0
        
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            page_text = page.get_text().strip()
            if page_text:
                text += page_text + "\n"
                pages_processed += 1
        
        pdf_document.close()
        
        if not text.strip():
            raise HTTPException(status_code=400, detail="O PDF não contém texto extraível.")
        
        # Limpar vectorstore existente para a sessão
        if session_id in user_vectorstores:
            del user_vectorstores[session_id]
            logger.info(f"Vectorstore anterior removido para sessão {session_id}")
        
        # Criar e armazenar novo vectorstore
        chunks = text_splitter.create_documents([text])
        vectorstore = Chroma.from_documents(chunks, embeddings)
        user_vectorstores[session_id] = vectorstore
        
        logger.info(f"Documento processado para sessão {session_id}: {pages_processed} páginas, {len(chunks)} chunks")
        
        return UploadResponse(
            status="success", 
            message="Documento carregado e processado com sucesso.",
            session_id=session_id,
            pages_processed=pages_processed
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro no processamento do documento: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao processar o arquivo: {str(e)}")

# --- Endpoint para Consultas ao Agente --- CORRIGIDO
@app.post("/query", response_model=QueryResponse)
async def query_agent(query: Query):
    """
    Faz uma pergunta sobre o documento carregado na sessão especificada.
    """
    logger.info(f"Consulta recebida para sessão: {query.session_id}")
    logger.debug(f"Sessões ativas: {list(user_vectorstores.keys())}")
    
    # Verificar se a sessão existe e tem documento carregado
    if query.session_id not in user_vectorstores:
        logger.warning(f"Sessão {query.session_id} não encontrada ou sem documento carregado")
        return QueryResponse(
            response="❌ Nenhum documento foi carregado para esta sessão. Por favor, carregue um documento primeiro usando o endpoint /upload_document.",
            session_id=query.session_id
        )
    
    try:
        # Preparar a entrada para o agente incluindo o session_id
        agent_input = {
            "input": f"session_id: {query.session_id}\npergunta: {query.input}",
            "session_id": query.session_id
        }
        
        response = with_history.invoke(
            agent_input,
            config={"configurable": {"session_id": query.session_id}}
        )
        
        output = response.get("output", "Não foi possível obter uma resposta.")
        return QueryResponse(response=output, session_id=query.session_id)
    
    except Exception as e:
        logger.error(f"Erro na consulta para sessão {query.session_id}: {e}")
        return QueryResponse(
            response="⚠️ Desculpe, ocorreu um erro ao processar sua pergunta. Tente novamente ou recarregue o documento.",
            session_id=query.session_id
        )

# --- Endpoint alternativo mais simples ---
@app.post("/query_simple", response_model=QueryResponse)
async def query_simple(input: str = Form(...), session_id: str = Form(...)):
    """
    Versão simplificada do endpoint de consulta usando FormData.
    """
    return await query_agent(Query(input=input, session_id=session_id))

# --- Endpoint para listar sessões ativas ---
@app.get("/sessions")
async def list_sessions():
    """Lista todas as sessões ativas com documentos carregados"""
    return {
        "active_sessions": list(user_vectorstores.keys()),
        "total_sessions": len(user_vectorstores)
    }

# --- Endpoint para verificar se sessão existe ---
@app.get("/sessions/{session_id}")
async def check_session(session_id: str):
    """Verifica se uma sessão específica existe e tem documento carregado"""
    exists = session_id in user_vectorstores
    return {
        "session_id": session_id,
        "exists": exists,
        "has_document": exists
    }

# --- Endpoint para limpar sessão ---
@app.delete("/sessions/{session_id}")
async def clear_session(session_id: str):
    """Remove uma sessão específica"""
    if session_id in user_vectorstores:
        del user_vectorstores[session_id]
        
        # Limpar histórico do chat também
        try:
            history = get_chat_history(session_id)
            history.clear()
            logger.info(f"Histórico da sessão {session_id} limpo")
        except Exception as e:
            logger.warning(f"Erro ao limpar histórico da sessão {session_id}: {e}")
            
        return {"status": "success", "message": f"Sessão {session_id} removida."}
    else:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)