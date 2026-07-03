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

        Handles multi-topic queries (e.g. "chemical messengers, nicotine,
        amphetamines") by searching for each topic separately and merging
        the results, since a single combined-query embedding tends to bury
        chunks that are highly relevant to only one of several topics.

        Args:
            query: The topics/query to search for (may contain multiple
                comma/semicolon/"and"-separated topics)
            similarity_threshold: Minimum similarity score (0-1) to start from

        Returns:
            List of ALL relevant text chunks
        """
        if not self.vector_store:
            raise ValueError("Vector store not initialized")

        # Split into individual topics so each one gets its own search,
        # otherwise a query embedding for several topics at once dilutes
        # similarity to material that only covers a subset of them.
        import re
        sub_topics = [t.strip() for t in re.split(r',|;|\band\b', query, flags=re.IGNORECASE) if t.strip()]
        if not sub_topics:
            sub_topics = [query]

        # Keep the retrieved set focused and bounded: the best-matching
        # chunks per topic, capped overall. This keeps the study guide
        # relevant-only (not a dump of everything above a low bar) while
        # still giving narrow/single-topic queries enough material to
        # produce a substantive guide.
        #
        # Note: short/bare-word queries (e.g. a single topic like
        # "plasticity" with no surrounding context) tend to score much
        # lower on cosine similarity against this embedding model than
        # longer queries do, even against genuinely relevant paragraphs.
        # So a fixed absolute similarity floor can zero out an entire
        # narrow topic. To avoid that, candidates are gathered using only a
        # low sanity floor (to drop clearly unrelated content) and ranked
        # by relative similarity, then the target threshold is used to
        # decide how many of the top-ranked candidates look "confidently"
        # relevant vs. just "best available" — never fewer than
        # MIN_DESIRED_CHUNKS if the document has enough content at all.
        MAX_CHUNKS_PER_TOPIC = 20
        MAX_TOTAL_CHUNKS = 40
        MIN_DESIRED_CHUNKS = 10
        SANITY_FLOOR = 0.15

        try:
            self._setup_event_loop()

            search_k = min(len(self.chunks), 50)

            # Collect best score per unique chunk content across all sub-topic searches
            best_by_content = {}

            for sub_topic in sub_topics:
                print(f"[RAG] Performing similarity search for topic: '{sub_topic}' (k={search_k})...")
                results_with_scores = self.vector_store.similarity_search_with_score(sub_topic, k=search_k)

                topic_matches = []
                for doc, score in results_with_scores:
                    # Embeddings are normalized, so squared L2 distance maps
                    # directly to cosine similarity: sim = 1 - (dist / 2)
                    similarity = 1 - (score / 2.0)
                    if similarity >= SANITY_FLOOR:
                        topic_matches.append((doc.page_content, similarity))

                # Only keep this topic's best-ranked matches, not everything above the floor
                topic_matches.sort(key=lambda x: x[1], reverse=True)
                for content, similarity in topic_matches[:MAX_CHUNKS_PER_TOPIC]:
                    if content not in best_by_content or similarity > best_by_content[content]:
                        best_by_content[content] = similarity

            def collect_above(threshold):
                chunks = [
                    {'content': content, 'similarity': sim}
                    for content, sim in best_by_content.items()
                    if sim >= threshold
                ]
                chunks.sort(key=lambda x: x['similarity'], reverse=True)
                return chunks

            # Progressively relax the threshold until we have a reasonable
            # minimum amount of material, but never exceed the overall cap.
            relevant_chunks = collect_above(similarity_threshold)
            threshold = similarity_threshold
            while len(relevant_chunks) < MIN_DESIRED_CHUNKS and threshold > SANITY_FLOOR:
                threshold = round(threshold - 0.1, 2)
                print(f"[RAG] Only {len(relevant_chunks)} chunks found, lowering threshold to {threshold}...")
                relevant_chunks = collect_above(threshold)

            # Rank-based fallback: if the document simply doesn't have much
            # scoring above even the sanity floor (common for short/narrow
            # queries), still take the best-available candidates up to
            # MIN_DESIRED_CHUNKS rather than returning a near-empty guide.
            if len(relevant_chunks) < MIN_DESIRED_CHUNKS:
                all_ranked = collect_above(0.0)
                if len(all_ranked) > len(relevant_chunks):
                    print(f"[RAG] Still only {len(relevant_chunks)} chunks above sanity floor, "
                          f"falling back to the {min(MIN_DESIRED_CHUNKS, len(all_ranked))} best-ranked chunks overall...")
                    relevant_chunks = all_ranked[:MIN_DESIRED_CHUNKS]

            relevant_chunks = relevant_chunks[:MAX_TOTAL_CHUNKS]

            # DEBUG: Print similarity scores
            print(f"\n[RAG DEBUG] Using {len(relevant_chunks)} relevant chunks (final threshold={threshold}):")
            for i, chunk in enumerate(relevant_chunks[:5], 1):
                print(f"  Chunk {i}: Similarity = {chunk['similarity']:.3f}")
            if len(relevant_chunks) > 5:
                print(f"  ... and {len(relevant_chunks) - 5} more chunks")

            relevant_content = [chunk['content'] for chunk in relevant_chunks]

            return relevant_content

        except Exception as e:
            print(f"[RAG] Error in similarity search: {e}")
            import traceback
            traceback.print_exc()
            # Fallback: return top chunks without scoring
            print("[RAG] Falling back to simple similarity search...")
            try:
                results = self.vector_store.similarity_search(query, k=30)
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