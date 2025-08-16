
import os
from fastapi import FastAPI
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Dict, Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent

load_dotenv()

assert "OPENAI_API_KEY" in os.environ, "Please set the OPENAI_API_KEY environment variable."

db_products = {
    "phone1": {"name": "Phone Model A", "price": 299.99, "description": "A great phone with many features."},
    "head'phones1": {"name": "Headphones Model B", "price": 89.99, "description": "Noise-cancelling headphones."},
    "laptop1": {"name": "Laptop Model C", "price": 999.99, "description": "A powerful laptop for professionals."},
    "politics": {
        "guarantee": "We guarantee the best prices and quality.",
        "return_policy": "You can return products within 30 days for a full refund.",
        "customer_service": "Our customer service is available 24/7 to assist you with any inquiries.",     
        "shipping_info": "We offer free shipping on orders over $50.",
        "payment_methods": "We accept all major credit cards, PayPal, and bank transfers."    
    }
}

@tool
def get_product_info(product_id: str) -> Dict[str, Any]:
    """
    Get information about a product by its ID.
    """
    query = product_id.lower().replace("'", "_")
    
    if query in db_products:
        return db_products[query]
    else:
        return {"error": f"Product {db_products[query]} not found."}  
    
    

model = ChatOpenAI(
    model="gpt-4o",
    temperature=0,
    max_tokens=1000,
    openai_api_key=os.environ["OPENAI_API_KEY"]
)

tool_names = [get_product_info]    

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "You are a helpful assistant that provides product information."), 
        ("placeholder", "{chat_history}"),
        ("user", "{input}"),
        ("assistant", "Here is the information you requested: {output}"),
        ("placeholder", "{agent_scratchpad}")
    ] 
)

agent = create_tool_calling_agent(
    llm=model,
    tools=tool_names,
    prompt=prompt,  
)  

app = FastAPI()

class Query(BaseModel):
    input: str  

@app.post("/query")
async def query_agent(query: Query):
    """
    Endpoint to query the agent with a product-related question.
    """
    agent_executor = AgentExecutor(agent=agent, tools=[get_product_info], verbose=True)
    response = await agent_executor.arun(query.input)
    
    return {"response": response}