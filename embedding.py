"""
Fixed Embedding Module - Using FAISS instead of ChromaDB
FAISS is more stable and doesn't have event loop issues
"""

import os
import pickle
# from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

def get_embeddings():
    """Get HuggingFace embeddings (FREE, runs locally, no API needed)"""
    print("[Embedding] Using HuggingFace local embeddings (no API required)")
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",  # Fast and efficient
        model_kwargs={'device': 'cpu'},  # Use 'cuda' if you have GPU
        encode_kwargs={'normalize_embeddings': True}
    )

# def get_embeddings():
#     """Get Google Gemini embeddings instance"""
#     api_key = os.getenv("GOOGLE_API_KEY")
#     if not api_key:
#         raise ValueError("Google API key not found. Please set GOOGLE_API_KEY in your .env file")
    
#     genai.configure(api_key=api_key)
    
#     return GoogleGenerativeAIEmbeddings(
#         model="models/embedding-001"
#     )


def create_vector_store(text_chunks: list, persist_directory: str = None):
    """
    Takes text chunks, embeds them using Google Gemini model,
    and stores them in a FAISS vector database.

    Args:
        text_chunks (list): A list of text chunks (strings).
        persist_directory (str, optional): Directory to persist the vector store.

    Returns:
        FAISS: The initialized FAISS vector store object.
    """
    
    print(f"[Embedding] Creating vector store with {len(text_chunks)} chunks...")
    
    # Set default persist directory if none provided
    if not persist_directory:
        persist_directory = "./faiss_store"
    
    # Ensure directory exists
    os.makedirs(persist_directory, exist_ok=True)
    
    # Get embeddings
    gemini_embeddings = get_embeddings()
    
    try:
        # Create FAISS vector store from text chunks
        print("[Embedding] Generating embeddings and storing in FAISS...")
        vectorstore = FAISS.from_texts(
            texts=text_chunks,
            embedding=gemini_embeddings
        )
        
        # Save to disk
        vectorstore.save_local(persist_directory)
        
        print(f"✅ Vector store created and saved at {persist_directory}")
        return vectorstore
        
    except Exception as e:
        print(f"❌ Error creating vector store: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def load_vector_store(persist_directory: str = "./faiss_store"):
    """
    Load an existing vector store from disk
    
    Args:
        persist_directory: Path to the saved vector store
        
    Returns:
        FAISS vector store instance
    """
    
    print(f"[Embedding] Loading vector store from {persist_directory}...")
    
    # Get embeddings
    gemini_embeddings = get_embeddings()
    
    try:
        # Load FAISS vector store
        vectorstore = FAISS.load_local(
            persist_directory,
            gemini_embeddings,
            allow_dangerous_deserialization=True
        )
        
        print(f"✅ Vector store loaded successfully from {persist_directory}")
        return vectorstore
        
    except Exception as e:
        print(f"❌ Error loading vector store: {str(e)}")
        import traceback
        traceback.print_exc()
        raise