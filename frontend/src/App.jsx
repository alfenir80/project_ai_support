import { useState } from "react";
import './App.css';

function App() {

  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");

  const handleSendMessage = async(e) => {

    e.preventDefault();
    if (!input.trim()) return;  

    const userMessage = { text: input, sender: "user" };
    setMessages(prevMessages => [...prevMessages, userMessage]);

    setInput("");

    try {

      const response = await fetch("http://127.0.0.1:8000/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        // CORRIGIDO: Agora usa a chave 'input'
        body: JSON.stringify({ input: input })
      });

      if (!response.ok) {
        throw new Error("Network response was not ok");
      }

      const data = await response.json();
      // CORRIGIDO: Agora usa a chave 'response'
      const botMessage = { text: data.response, sender: "bot" };
      setMessages(prevMessages => [...prevMessages, botMessage]);

    }
    catch (error) {
      console.error("Error fetching data:", error);
      const errorMessage = { text: "Error: Unable to get response from server.", sender: "bot" };
      setMessages(prevMessages => [...prevMessages, errorMessage]);
    }
  }; 
  
  return (
    <div className="App">
      <div className="chat-container">
        <div className="messages">
          {messages.map((msg, index) => (
            <div key={index} className={`message ${msg.sender}`}>
              {msg.text}
            </div>
          ))}
        </div>
        <form onSubmit={handleSendMessage} className="input-form">
          <input 
            type="text" 
            value={input} 
            onChange={(e) => setInput(e.target.value)} 
            placeholder="Type your message..." 
            className="input-field"
          />
          <button type="submit" className="send-button">Send</button>
        </form>
      </div>
    </div>
  );
};

export default App;

