import { useState, useEffect } from "react";
import { v4 as uuidv4 } from "uuid";
// Import Bootstrap CSS
import 'bootstrap/dist/css/bootstrap.min.css';
// Import custom CSS if you have specific overrides or additional styles
import './App.css'; // Uncomment if you have a custom App.css you want to keep

// Helper function to get or create a session ID from localStorage
function getSessionId() {
  let sessionId = localStorage.getItem("sessionId");
  if (!sessionId) {
    sessionId = uuidv4();
    localStorage.setItem("sessionId", sessionId);
  }
  return sessionId;
}

function App() {
  // Estados da aplicação
  // O sessionId é gerado uma única vez
  const [sessionId] = useState(getSessionId()); 
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [file, setFile] = useState(null);
  const [isLoading, setIsLoading] = useState(false); // Para indicar carregamento

  // CORRIGIDO: Esta função deve apenas armazenar o arquivo selecionado
  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  // Funções de envio de mensagem e upload de arquivo separadas
  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = { id: sessionId, text: input, sender: "user" };
    setMessages((prevMessages) => [...prevMessages, userMessage]);
    setIsLoading(true);

    try {
      const response = await fetch("http://127.0.0.1:8000/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          input: input,
          session_id: sessionId,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      const botMessage = { id: sessionId, text: data.response, sender: "bot" };
      setMessages((prevMessages) => [...prevMessages, botMessage]);
    } catch (error) {
      console.error("Error fetching data:", error);
      const errorMessage = {
        id: sessionId,
        text: "Ocorreu um erro ao obter a resposta do servidor.",
        sender: "bot",
      };
      setMessages((prevMessages) => [...prevMessages, errorMessage]);
    } finally {
      setIsLoading(false);
      setInput("");
    }
  };

  const handleFileUpload = async () => {
    if (!file) {
      setMessages((prevMessages) => [
        ...prevMessages,
        { id: sessionId, text: "Por favor, selecione um arquivo para enviar.", sender: "bot" },
      ]);
      return;
    }

    const formData = new FormData();
    // CORRIGIDO: Adicionar o session_id ao formData
    formData.append("session_id", sessionId); 
    formData.append("file", file);

    setMessages((prevMessages) => [
      ...prevMessages,
      { id: sessionId, text: `Enviando arquivo: ${file.name}...`, sender: "bot" },
    ]);
    setIsLoading(true);

    try {
      const response = await fetch("http://127.0.0.1:8000/upload_document", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      setMessages((prevMessages) => {
        const newMessages = prevMessages.slice(0, -1);
        return [...newMessages, { id: sessionId, text: result.message, sender: "bot" }];
      });
      setFile(null); // Limpa o estado do arquivo
    } catch (error) {
      console.error("Error uploading file:", error);
      setMessages((prevMessages) => {
        const newMessages = prevMessages.slice(0, -1);
        return [
          ...newMessages,
          { id: sessionId, text: "Ocorreu um erro ao enviar o arquivo.", sender: "bot" },
        ];
      });
    } finally {
      setIsLoading(false);
    }
  };

  const isSendButtonDisabled = !input.trim() || isLoading;

  return (
    <div className="container mt-4">
      <h1 className="text-center mb-4">Assistente de Suporte IA</h1>

      <div className="chat-window card mb-4">
        <div className="card-body d-flex flex-column">
          {messages.length === 0 && !isLoading && (
            <div className="welcome-message text-center text-muted flex-grow-1 d-flex align-items-center justify-content-center">
              <p className="lead">Faça o upload de um documento PDF e comece a fazer perguntas!</p>
            </div>
          )}
          {isLoading && (
            <div className="text-center flex-grow-1 d-flex align-items-center justify-content-center">
              <div className="spinner-border text-primary" role="status">
                <span className="visually-hidden">Carregando...</span>
              </div>
            </div>
          )}
          {messages.map((msg) => (
            <div key={msg.id} className={`message ${msg.sender} mb-2`}>
              {msg.text}
            </div>
          ))}
        </div>
      </div>

      <div className="input-area card p-3">
        <div className="row g-2 align-items-center">

          <div className="col-auto">
            <label htmlFor="file-input" className="btn btn-outline-primary me-2 custom-file-upload-label">
              Escolher PDF
            </label>
            <input
              id="file-input"
              type="file"
              onChange={handleFileChange}
              className="file-input-hidden"
              accept=".pdf"
            />
            {file && <span className="file-name text-muted me-2">{file.name}</span>}
          </div>
          <div className="col-auto">
            <button
              type="button"
              onClick={handleFileUpload}
              className="btn btn-primary me-2"
              disabled={!file || isLoading}
            >
              Enviar Documento
            </button>
          </div>

          <div className="col">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Digite sua mensagem..."
              className="form-control me-2"
              disabled={isLoading}
            />
          </div>
          <div className="col-auto">
            <button
              type="submit"
              onClick={handleSendMessage}
              className="btn btn-success send-button"
              disabled={isSendButtonDisabled}
            >
              Enviar Mensagem
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;