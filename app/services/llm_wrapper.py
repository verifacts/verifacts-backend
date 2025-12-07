import os
import logging 
from typing import List, Dict, Any, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from dotenv import load_dotenv

from app.core.config import config

load_dotenv()  # Load environment variables from a .env file if present

class LLMWrapper:
    """
    Centralized LLM Wrapper for the Verifacts System.
    
    Standardizes model configurations, message formatting, and response handling.
    """
    
    _instance = None
    
    def __init__(self):
        self.model_name = config.LLM_MODEL_NAME
        self.temperature = config.LLM_TEMPERATURE
        self.max_tokens = config.LLM_MAX_TOKEN
        self.api_key = config.GEMINI_API_KEY
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set in the environment variables.")
            self.llm = None
            
        self.llm = ChatGoogleGenerativeAI(
            model_name=self.model_name,
            temperature=self.temperature,
            max_output_tokens=self.max_tokens,
            api_key=self.api_key
        )
        
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    
    def get_llm(self):
        """Returns the underlying LLM instance."""
        return self.llm
    

llm_wrapper = LLMWrapper.get_instance()

