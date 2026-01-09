"""
Simplified RAG Pipeline for Study Material Only
Returns ALL relevant chunks, not just a fixed number
Fixed for Flask threading issues
"""

import os
import sys
import asyncio
from pdf_extracter import extract_pdf_to_text_file
from text_chunks import get_text_chunks
from embedding import create_vector_store
from typing import List
import numpy as np

# Fix for Windows/Flask threading
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class RAGPipeline:
    """
    Simplified RAG pipeline for study material
    """
    
    def __init__(self):
        self.vector_store = None
        self.chunks = []
        self.raw_text = ""
    
    # Function 1
    def process_document(
        self, 
        file_path: str,
        topics: str,
        extracted_text_folder: str = "./extracted_text",
        persist_directory: str = None,
        similarity_threshold: float = 0.5
    ) -> dict:
        """
        Main processing function
        
        Args:
            file_path: Path to the uploaded PDF file
            topics: Topics the user wants to study
            extracted_text_folder: Where to save extracted text
            persist_directory: Where to save the vector store
            similarity_threshold: Minimum similarity score (0-1) to include a chunk
            
        Returns:
            dict with processed data and ALL relevant chunks
        """
        try:
            # Ensure event loop exists for this thread
            self._setup_event_loop()
            
            print(f"[RAG] Processing study material: {file_path}")
            

            # Step 1: Extract text from PDF and save to file
            print("[RAG] Step 1: Extracting text from PDF...")
            extraction_result = extract_pdf_to_text_file(file_path, extracted_text_folder)
            
            if not extraction_result['success']:
                raise ValueError("Failed to extract text from PDF")
            
            self.raw_text = extraction_result['text']
            print(f"[RAG] Extracted {len(self.raw_text)} characters")
            

            # Step 2: Chunk the text
            print("[RAG] Step 2: Creating text chunks...")
            self.chunks = get_text_chunks(self.raw_text)
            print(f"[RAG] Created {len(self.chunks)} chunks")
            
            if not self.chunks:
                raise ValueError("No text chunks created")
            

            # Step 3: Create vector store with embeddings
            print("[RAG] Step 3: Creating vector store with embeddings...")
            self.vector_store = create_vector_store(
                self.chunks, 
                persist_directory=persist_directory
            )
            print("[RAG] Vector store created successfully")
            

            # Step 4: Query for ALL relevant content
            print(f"[RAG] Step 4: Finding ALL relevant chunks for topics: {topics}")
            relevant_chunks = self._get_all_relevant_content(
                topics, 
                similarity_threshold=similarity_threshold
            )
            
            print(f"[RAG] Found {len(relevant_chunks)} relevant chunks (out of {len(self.chunks)} total)")
            
            return {
                'success': True,
                'vector_store': self.vector_store,
                'chunks': self.chunks,
                'relevant_chunks': relevant_chunks,
                'total_chunks': len(self.chunks),
                'relevant_count': len(relevant_chunks),
                'topics': topics,
                'extracted_text_file': extraction_result['output_file']
            }
            
        except Exception as e:
            print(f"[RAG ERROR] {str(e)}")
            import traceback
            traceback.print_exc()
            raise Exception(f"RAG Pipeline failed: {str(e)}")
    

    # Function 2
    def _setup_event_loop(self):
        """Ensure an event loop exists for the current thread"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("Event loop is closed")
        except RuntimeError:
            # No event loop in this thread, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            print("[RAG] Created new event loop for thread")
    

    # Function 3
    def _get_all_relevant_content(
        self, 
        query: str, 
        similarity_threshold: float = 0.5
    ) -> List[str]:
        """
        Retrieve ALL relevant chunks based on similarity threshold.
        Instead of limiting to top k, we return all chunks above a threshold.
        
        Args:
            query: The topics/query to search for
            similarity_threshold: Minimum similarity score (0-1)
            
        Returns:
            List of ALL relevant text chunks
        """
        if not self.vector_store:
            raise ValueError("Vector store not initialized")
        
        try:
            # Ensure event loop
            self._setup_event_loop()
            
            # First, get a large number of results with scores
            # We'll get all chunks, then filter by score
            
            k = min(len(self.chunks), 100)  # Start with top 100 or all chunks
            
            print(f"[RAG] Performing similarity search (k={k})...")
            results_with_scores = self.vector_store.similarity_search_with_score(query, k=k)
            
            # Filter by similarity threshold
            # Note: ChromaDB returns DISTANCE, not similarity
            # Lower distance = higher similarity
            # We need to convert or adjust threshold
            relevant_chunks = []
            
            print(f"[RAG] Filtering by relevance...")
            for doc, score in results_with_scores:
                # ChromaDB uses distance metrics (lower is better)
                # Typical range: 0.0 (identical) to 2.0 (very different)
                # We convert to similarity: 1 - (distance / 2)
                similarity = 1 - (score / 2.0)
                
                if similarity >= similarity_threshold:
                    relevant_chunks.append({
                        'content': doc.page_content,
                        'similarity': similarity,
                        'distance': score
                    })
            
            # Sort by similarity (highest first)
            relevant_chunks.sort(key=lambda x: x['similarity'], reverse=True)
            
            # DEBUG: Print similarity scores
            print(f"\n[RAG DEBUG] Similarity scores:")
            for i, chunk in enumerate(relevant_chunks[:5], 1):
                print(f"  Chunk {i}: Similarity = {chunk['similarity']:.3f}, Distance = {chunk['distance']:.3f}")
            if len(relevant_chunks) > 5:
                print(f"  ... and {len(relevant_chunks) - 5} more chunks")
            
            # If we got very few results, lower the threshold and try again
            if len(relevant_chunks) < 3 and similarity_threshold > 0.3:
                print(f"[RAG] Only {len(relevant_chunks)} chunks found, lowering threshold to 0.3...")
                return self._get_all_relevant_content(query, similarity_threshold=0.3)
            
            # Extract just the content
            relevant_content = [chunk['content'] for chunk in relevant_chunks]
            
            return relevant_content
            
        except Exception as e:
            print(f"[RAG] Error in similarity search: {e}")
            import traceback
            traceback.print_exc()
            # Fallback: return top 10 chunks without scoring
            print("[RAG] Falling back to simple similarity search...")
            try:
                results = self.vector_store.similarity_search(query, k=10)
                return [doc.page_content for doc in results]
            except:
                print("[RAG] Fallback also failed, returning empty list")
                return []
    

    # Function 4
    def query_vector_store(self, query: str, threshold: float = 0.5) -> List[str]:
        """
        Query the vector store for additional questions
        """
        return self._get_all_relevant_content(query, threshold)


# For testing
if __name__ == "__main__":
    print("=" * 60)
    print("RAG Pipeline - Command Line Interface")
    print("=" * 60)
    print("\nNOTE: This script is designed to be called by Flask.")
    print("For web interface, please run: python app.py")
    print("=" * 60)
    
    # Simple CLI for testing
    try:
        pdf_path = input("\nEnter PDF path (or press Enter to exit): ")
        if not pdf_path:
            exit()
            
        if not os.path.exists(pdf_path):
            print(f"Error: File not found at {pdf_path}")
            exit()
        
        topics = input("Enter topics to study: ").strip()
        
        # Process
        pipeline = RAGPipeline()
        result = pipeline.process_document(
            file_path=pdf_path,
            topics=topics,
            extracted_text_folder="./extracted_text",
            persist_directory="./chroma_store_cli"
        )
        
        print("\n" + "=" * 60)
        print("PROCESSING COMPLETE")
        print("=" * 60)
        print(f"Total chunks: {result['total_chunks']}")
        print(f"Relevant chunks found: {result['relevant_count']}")
        print(f"Extracted text saved to: {result['extracted_text_file']}")
        
        print("\n--- Relevant Content Preview ---")
        for i, chunk in enumerate(result['relevant_chunks'][:3], 1):
            print(f"\nChunk {i}:")
            print(chunk[:200] + "...")
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()