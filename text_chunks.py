from langchain_text_splitters import RecursiveCharacterTextSplitter

def get_text_chunks(text: str) -> list:
    """
    Splits a large document text into smaller, manageable chunks.

    Args:
        text (str): The raw text from the document.

    Returns:
        list: A list of text chunks.
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, 
        chunk_overlap=100, 
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )
    
    chunks = text_splitter.split_text(text)
    return chunks