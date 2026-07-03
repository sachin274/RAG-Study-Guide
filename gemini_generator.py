"""
Gemini API Integration for Study Guide Generation
Processes text chunks with Gemini to create structured study content
"""

import os
import re
import google.generativeai as genai
from dotenv import load_dotenv
import time

load_dotenv()


_ALREADY_STRUCTURED_BLOCK = re.compile(r'^(#{1,6}\s|[-*]\s|\d+\.\s|>|\||```)')


def _fix_inline_bullets(markdown_text: str) -> str:
    """
    Gemini occasionally writes list items inline within a prose paragraph
    instead of as separate list lines (e.g. "reasons: - During youth. -
    After injury."), and also soft-wraps long paragraphs across multiple
    single newlines. Pandoc treats consecutive non-blank lines as one
    paragraph, so both cases render as a single run-on paragraph instead of
    a bullet list. This collapses each prose paragraph block to one line,
    then splits any inline "- item" sequence (preceded by a period or
    colon) onto its own bullet lines.
    """
    # Gemini sometimes omits the blank line between a heading and the
    # paragraph that follows it. Without a blank line the two are one block
    # below, and since it starts with "#" it would be skipped entirely
    # (including any inline-bullet paragraph riding along with it). Force a
    # blank line after every heading line first so headings always become
    # their own block.
    markdown_text = re.sub(r'(^#{1,6}[^\n]*)\n(?!\n)', r'\1\n\n', markdown_text, flags=re.MULTILINE)

    blocks = markdown_text.split('\n\n')
    fixed_blocks = []
    for block in blocks:
        stripped = block.strip()
        if not stripped or _ALREADY_STRUCTURED_BLOCK.match(stripped):
            fixed_blocks.append(block)
            continue

        collapsed = re.sub(r'\s*\n\s*', ' ', stripped)
        if re.search(r'[.:]\s+-\s+\S', collapsed):
            parts = re.split(r'(?<=[.:])\s+-\s+', collapsed)
            items = [f"- {part.strip()}" for part in parts[1:] if part.strip()]
            if items:
                fixed_blocks.append(parts[0] + '\n\n' + '\n'.join(items))
                continue

        fixed_blocks.append(block)
    return '\n\n'.join(fixed_blocks)


def generate_study_content_with_gemini(relevant_chunks: list, topics: str, custom_prompt: str = None) -> str:
    """
    Send relevant chunks to Gemini API to generate structured study guide content
    
    Args:
        relevant_chunks: List of text chunks relevant to the topics
        topics: Topics the user wants to study
        custom_prompt: Optional custom prompt for Gemini (you can modify this)
    
    Returns:
        str: Generated study guide content from Gemini
    """
    
    print("\n" + "="*80)
    print("[Gemini] Starting content generation")
    print("="*80)
    
    # Get API key
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        error_msg = "Google API key not found in .env file"
        print(f"[Gemini] ❌ ERROR: {error_msg}")
        raise ValueError(error_msg)
    
    print(f"[Gemini] ✅ API key found (length: {len(api_key)})")
    
    # Configure Gemini
    try:
        genai.configure(api_key=api_key)
        print("[Gemini] ✅ API configured successfully")
    except Exception as e:
        print(f"[Gemini] ❌ ERROR configuring API: {str(e)}")
        raise
    
    # Use Gemini 2.5 Flash (stable version)
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        print("[Gemini] ✅ Model initialized: gemini-2.5-flash")
    except Exception as e:
        print(f"[Gemini] ❌ ERROR initializing model: {str(e)}")
        raise
    
    print(f"[Gemini] Processing {len(relevant_chunks)} chunks for topics: {topics}")
    
    # Combine all chunks into one text
    combined_text = "\n\n---\n\n".join(relevant_chunks)
    print(f"[Gemini] Combined text length: {len(combined_text)} characters")

    # Limit text length to avoid token limits and keep generation fast.
    # The retrieval step already caps chunks to the ~40 best matches, so
    # this is mostly a safety net.
    MAX_CHARS = 65000
    if len(combined_text) > MAX_CHARS:
        print(f"[Gemini] ⚠️  Text too long, truncating to {MAX_CHARS} characters")
        combined_text = combined_text[:MAX_CHARS] + "\n\n[... content truncated due to length ...]"

    # Default prompt (YOU CAN MODIFY THIS)
    if not custom_prompt:
        custom_prompt = f"""
You are an expert study guide creator writing for a student who needs to genuinely learn this material. Based on the provided study material and topics, create a focused, well-structured study guide that will be converted to PDF.

**Topics to focus on:** {topics}

**Study Material (excerpts retrieved for relevance to the topics above):**
{combined_text}

**Instructions:**
1. If multiple topics are listed, give each topic its own section, but only include what is genuinely relevant — do not pad, repeat points, or add tangential detail just to fill space.
2. For each topic, cover ALL the distinct relevant sub-points, mechanisms, and examples found in the retrieved material below — not just one sentence per topic. Use a short paragraph plus a few bullet points where useful (e.g. listing types, causes, effects, or examples) rather than compressing everything into a single line. Do not restate the same point multiple times, and do not invent details that aren't in the material.
3. Prioritize relevance over padding — leave out only details that are truly repetitive or add no value — but do not under-explain a topic just to keep the guide short.
4. Structure the content with clear headings and subheadings using proper markdown hierarchy.
5. Highlight the most important terms/facts students should memorize using **bold**, but do not bold everything.
6. Aim for a guide that is genuinely thorough enough to teach the topics well — a student should come away with a solid understanding, not a one-paragraph summary.
7. Do NOT add a glossary/key terms list, review/practice questions, or a study tips section — the guide should contain only the topic content itself.
8. **IMPORTANT — Markdown formatting rules for clean PDF conversion:**
   - Do NOT start your response with a top-level `#` title — start directly with a `##` section heading (the document title is added separately).
   - Use `##` for main sections, `###` for subsections, `####` for finer breakdowns if needed.
   - Use **bold** for emphasis, *italic* for secondary emphasis.
   - Use bullet points (-) and numbered lists (1., 2., 3.) — each bullet/list item MUST start on its own new line (never write multiple "- item" or "* item" entries inline on the same line).
   - Use code blocks with ``` only for actual code or technical syntax.
   - Use > blockquotes for important callouts, warnings, or notable quotes from the material.
   - Keep paragraphs well-spaced with a blank line between blocks.
   - Avoid emojis or special characters that may not render in PDF.

Generate the study guide now (favor a concise, focused guide over an exhaustive one):
"""
    
    print(f"[Gemini] Prompt length: {len(custom_prompt)} characters")
    
    try:
        print("[Gemini] 🚀 Sending request to Gemini API...")
        print("[Gemini] This may take 10-30 seconds...")
        
        # Add retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Generate content with Gemini
                response = model.generate_content(
                    custom_prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.7,
                        top_p=0.95,
                        top_k=40,
                        max_output_tokens=12288,
                    ),
                    safety_settings=[
                        {
                            "category": "HARM_CATEGORY_HARASSMENT",
                            "threshold": "BLOCK_NONE",
                        },
                        {
                            "category": "HARM_CATEGORY_HATE_SPEECH",
                            "threshold": "BLOCK_NONE",
                        },
                        {
                            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                            "threshold": "BLOCK_NONE",
                        },
                        {
                            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                            "threshold": "BLOCK_NONE",
                        },
                    ]
                )
                
                # Check if response was blocked
                if not response.text:
                    print(f"[Gemini] ⚠️  Response blocked or empty")
                    if hasattr(response, 'prompt_feedback'):
                        print(f"[Gemini] Prompt feedback: {response.prompt_feedback}")
                    raise ValueError("Response was blocked by safety filters or is empty")
                
                print("[Gemini] ✅ Successfully generated study content")
                print(f"[Gemini] Response length: {len(response.text)} characters")
                print("="*80 + "\n")
                
                # Return the generated text
                return _fix_inline_bullets(response.text)
                
            except Exception as retry_error:
                print(f"[Gemini] ⚠️  Attempt {attempt + 1}/{max_retries} failed: {str(retry_error)}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    print(f"[Gemini] Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    raise
        
    except Exception as e:
        print(f"[Gemini] ❌ Error generating content: {str(e)}")
        print(f"[Gemini] Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        
        # Fallback: return a formatted version of the chunks
        print("[Gemini] 🔄 Falling back to basic formatting...")
        fallback_content = f"## Study Guide for: {topics}\n\n"
        fallback_content += "*Note: AI generation unavailable, showing extracted content*\n\n"
        fallback_content += f"*Error: {str(e)}*\n\n"
        fallback_content += "---\n\n"
        
        for i, chunk in enumerate(relevant_chunks[:10], 1):  # Limit to 10 chunks in fallback
            fallback_content += f"### Section {i}\n\n{chunk}\n\n---\n\n"
        
        if len(relevant_chunks) > 10:
            fallback_content += f"\n*Note: Showing 10 of {len(relevant_chunks)} relevant sections*\n"
        
        return fallback_content


def generate_study_content_with_custom_prompt(
    relevant_chunks: list, 
    topics: str, 
    custom_instructions: str
) -> str:
    """
    Alternative function that lets you pass completely custom instructions
    
    Args:
        relevant_chunks: List of text chunks
        topics: Topics to study
        custom_instructions: Your own custom prompt/instructions
    
    Returns:
        str: Generated content
    """
    
    combined_text = "\n\n---\n\n".join(relevant_chunks)
    
    # Limit text length
    MAX_CHARS = 50000
    if len(combined_text) > MAX_CHARS:
        combined_text = combined_text[:MAX_CHARS] + "\n\n[... content truncated ...]"
    
    full_prompt = f"""
{custom_instructions}

**Topics:** {topics}

**Study Material:**
{combined_text}
"""
    
    api_key = os.getenv("GOOGLE_API_KEY")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    try:
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        print(f"[Gemini] Error: {str(e)}")
        return f"Error generating content: {str(e)}"


# For testing
if __name__ == "__main__":
    print("="*80)
    print("Gemini Generator Module - Test Mode")
    print("="*80)
    
    # Test API key
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ No API key found in .env file")
        print("Please create a .env file with: GOOGLE_API_KEY=your_key_here")
    else:
        print(f"✅ API key found (length: {len(api_key)})")
        
        # Test simple generation
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            print("\nTesting Gemini 2.5 Flash API with simple prompt...")
            response = model.generate_content("Say 'Hello, Gemini 2.5 Flash is working!'")
            print(f"\n✅ Test successful!")
            print(f"Response: {response.text}")
            
        except Exception as e:
            print(f"\n❌ Test failed: {str(e)}")
            import traceback
            traceback.print_exc()