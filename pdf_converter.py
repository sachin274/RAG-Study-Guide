"""
PDF Converter using Pandoc
Converts markdown study guides to beautifully formatted PDFs
"""

import os
import subprocess
import shutil
import sys


# Styling injected into the HTML pandoc generates before wkhtmltopdf renders it to PDF.
# Passed via --include-in-header so it's self-contained (no relative CSS file to resolve).
PDF_STYLE = """
<style>
  body {
    font-family: 'Georgia', 'Times New Roman', serif;
    color: #232734;
    line-height: 1.65;
    font-size: 12pt;
  }

  #title-block-header {
    text-align: center;
    border-bottom: 3px solid #43B0AF;
    padding-bottom: 18px;
    margin-bottom: 30px;
  }
  #title-block-header .title {
    color: #2A3056;
    font-size: 2.1em;
    font-weight: 700;
    margin-bottom: 8px;
  }
  #title-block-header .author,
  #title-block-header .date {
    color: #43B0AF;
    font-size: 1.05em;
    font-style: normal;
  }

  h1, h2, h3, h4, h5 {
    font-family: 'Helvetica Neue', Arial, sans-serif;
    color: #1B4F4E;
    font-weight: 700;
    page-break-after: avoid;
  }
  h1 { font-size: 1.9em; border-bottom: 2px solid #43B0AF; padding-bottom: 8px; margin-top: 0.6em; }
  h2 { font-size: 1.5em; border-bottom: 1px solid #B7E4E3; padding-bottom: 5px; margin-top: 1.3em; color: #16716f; }
  h3 { font-size: 1.22em; margin-top: 1.1em; color: #1e8b88; }
  h4 { font-size: 1.05em; margin-top: 1em; color: #2A3056; }

  p { margin: 0.6em 0; text-align: justify; }

  strong { color: #145957; }

  ul, ol { margin: 0.5em 0 0.9em 0; padding-left: 1.6em; }
  li { margin-bottom: 0.35em; }

  blockquote {
    margin: 1em 0;
    padding: 0.6em 1em;
    border-left: 4px solid #43B0AF;
    background-color: #F0FAF9;
    color: #2A3056;
    font-style: italic;
  }

  table {
    border-collapse: collapse;
    width: 100%;
    margin: 1em 0 1.4em 0;
    font-size: 0.95em;
  }
  th, td {
    border: 1px solid #CFE3E2;
    padding: 8px 10px;
    text-align: left;
  }
  th { background-color: #E4F5F4; color: #145957; }
  tr:nth-child(even) td { background-color: #FAFDFD; }

  code {
    font-family: 'Consolas', 'Courier New', monospace;
    background-color: #F1F1F5;
    padding: 2px 5px;
    border-radius: 3px;
    font-size: 0.9em;
  }
  pre {
    background-color: #F1F1F5;
    border: 1px solid #DADCE5;
    border-radius: 6px;
    padding: 10px 12px;
    overflow-x: auto;
  }
  pre code { background: none; padding: 0; }

  hr {
    border: none;
    border-top: 1px solid #D8E8E7;
    margin: 1.6em 0;
  }

  #TOC {
    background-color: #F5FAFA;
    border: 1px solid #DDEFEE;
    border-radius: 6px;
    padding: 18px 24px;
    margin-bottom: 2em;
  }
  #TOC ul { list-style-type: none; padding-left: 1em; }
  #TOC > ul { padding-left: 0; }
  #TOC a { color: #16716f; text-decoration: none; }
  #TOC::before {
    content: "Contents";
    display: block;
    font-family: 'Helvetica Neue', Arial, sans-serif;
    font-weight: 700;
    font-size: 1.2em;
    color: #1B4F4E;
    margin-bottom: 10px;
  }
</style>
"""


def find_pandoc_path():
    """
    Try to find Pandoc executable in common locations
    
    Returns:
        str: Path to pandoc executable or 'pandoc' if in PATH
    """
    # Common Windows installation paths
    common_paths = [
        r"C:\Program Files\Pandoc\pandoc.exe",
        r"C:\Program Files (x86)\Pandoc\pandoc.exe",
        r"C:\Users\{}\AppData\Local\Pandoc\pandoc.exe".format(os.environ.get('USERNAME', '')),
        os.path.expanduser("~\\AppData\\Local\\Pandoc\\pandoc.exe"),
    ]
    
    # Check if pandoc is in PATH first
    try:
        result = subprocess.run(['pandoc', '--version'], 
                              capture_output=True, 
                              text=True, 
                              timeout=5,
                              shell=True)  # Use shell=True on Windows
        if result.returncode == 0:
            return 'pandoc'
    except:
        pass
    
    # Check common Windows paths
    if sys.platform == 'win32':
        for path in common_paths:
            if os.path.exists(path):
                print(f"[PDF Converter] Found Pandoc at: {path}")
                return path
    
    # Try using 'where' command on Windows to find pandoc
    if sys.platform == 'win32':
        try:
            result = subprocess.run(['where', 'pandoc'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5,
                                  shell=True)
            if result.returncode == 0:
                pandoc_path = result.stdout.strip().split('\n')[0]
                print(f"[PDF Converter] Found Pandoc at: {pandoc_path}")
                return pandoc_path
        except:
            pass
    
    # For Linux/Mac, use 'which'
    else:
        try:
            result = subprocess.run(['which', 'pandoc'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
    
    return None


def check_pandoc_installed():
    """
    Check if Pandoc is installed on the system
    
    Returns:
        tuple: (bool, str) - (is_installed, pandoc_path)
    """
    pandoc_path = find_pandoc_path()
    
    if not pandoc_path:
        print("[PDF Converter] ❌ Pandoc not found in common locations")
        return (False, None)
    
    try:
        result = subprocess.run([pandoc_path, '--version'], 
                              capture_output=True, 
                              text=True, 
                              timeout=5,
                              shell=(sys.platform == 'win32'))  # Use shell on Windows
        if result.returncode == 0:
            version = result.stdout.split('\n')[0]
            print(f"[PDF Converter] ✅ Pandoc found: {version}")
            return (True, pandoc_path)
        return (False, None)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"[PDF Converter] ❌ Error checking Pandoc: {str(e)}")
        return (False, None)


def convert_markdown_to_pdf(markdown_file: str, output_pdf: str, metadata: dict = None) -> dict:
    """
    Convert markdown file to PDF using Pandoc
    
    Args:
        markdown_file: Path to the input markdown file
        output_pdf: Path where the PDF should be saved
        metadata: Optional metadata dict with keys like 'title', 'author', 'date'
    
    Returns:
        dict: Result with success status and message
    """
    
    print("\n" + "="*80)
    print("[PDF Converter] Starting PDF conversion")
    print("="*80)
    
    # Check if Pandoc is installed and get its path
    is_installed, pandoc_path = check_pandoc_installed()
    
    if not is_installed:
        error_msg = (
            "Pandoc is not installed or not found in PATH. Please install it from https://pandoc.org/installing.html\n"
            "Or use: sudo apt-get install pandoc (Linux) / brew install pandoc (Mac) / "
            "Download installer (Windows)\n"
            "After installation, restart your terminal/IDE and try again."
        )
        print(f"[PDF Converter] ❌ {error_msg}")
        return {
            'success': False,
            'error': error_msg,
            'output_file': None
        }
    
    # Check if input file exists
    if not os.path.exists(markdown_file):
        error_msg = f"Markdown file not found: {markdown_file}"
        print(f"[PDF Converter] ❌ {error_msg}")
        return {
            'success': False,
            'error': error_msg,
            'output_file': None
        }
    
    print(f"[PDF Converter] Input file: {markdown_file}")
    print(f"[PDF Converter] Output file: {output_pdf}")
    print(f"[PDF Converter] Using Pandoc: {pandoc_path}")

    # Try simpler conversion first (no pdflatex - much faster!)
    print("[PDF Converter] Using fast conversion method (no LaTeX)...")

    # Write the CSS header include next to the output PDF so wkhtmltopdf
    # (which renders from a temp working dir) always gets an absolute path
    style_header_path = os.path.join(os.path.dirname(os.path.abspath(output_pdf)) or '.', '.pdf_style_header.html')
    with open(style_header_path, 'w', encoding='utf-8') as f:
        f.write(PDF_STYLE)

    # Build Pandoc command using wkhtmltopdf engine
    pandoc_command = [
        pandoc_path,
        markdown_file,
        '-o', output_pdf,
        '--pdf-engine=wkhtmltopdf',  # USE WKHTMLTOPDF INSTEAD
        '-V', 'margin-top=1in',
        '-V', 'margin-bottom=1in',
        '-V', 'margin-left=1in',
        '-V', 'margin-right=1in',
        '--include-in-header', style_header_path,
        '--toc',
        '--toc-depth=3',
    ]
    
    # Add metadata if provided
    if metadata:
        if metadata.get('title'):
            pandoc_command.extend(['-V', f"title={metadata['title']}"])
        if metadata.get('author'):
            pandoc_command.extend(['-V', f"author={metadata['author']}"])
        if metadata.get('date'):
            pandoc_command.extend(['-V', f"date={metadata['date']}"])
    
    try:
        print("[PDF Converter] 🚀 Running Pandoc conversion...")
        print(f"[PDF Converter] Command: {' '.join(pandoc_command)}")

        # Run Pandoc (longer timeout since guides are now much more detailed)
        result = subprocess.run(
            pandoc_command,
            capture_output=True,
            text=True,
            timeout=60,
            shell=(sys.platform == 'win32'),  # Use shell on Windows
            stdin=subprocess.DEVNULL  # Prevent any interactive prompts
        )

        if result.returncode == 0:
            if os.path.exists(output_pdf):
                print("[PDF Converter] ✅ PDF conversion successful!")
                print(f"[PDF Converter] Output: {output_pdf}")
                print(f"[PDF Converter] File size: {os.path.getsize(output_pdf)} bytes")
                print("="*80 + "\n")
                
                return {
                    'success': True,
                    'message': 'PDF generated successfully',
                    'output_file': output_pdf
                }
            else:
                error_msg = "PDF file was not created"
                print(f"[PDF Converter] ❌ {error_msg}")
                print(f"[PDF Converter] Pandoc output: {result.stdout}")
                print(f"[PDF Converter] Pandoc errors: {result.stderr}")
                return {
                    'success': False,
                    'error': error_msg,
                    'output_file': None
                }
        else:
            error_msg = f"Pandoc conversion failed (exit code {result.returncode})"
            print(f"[PDF Converter] ❌ {error_msg}")
            print(f"[PDF Converter] Stderr: {result.stderr}")
            
            return {
                'success': False,
                'error': f"{error_msg}: {result.stderr}",
                'output_file': None
            }
            
    except subprocess.TimeoutExpired:
        error_msg = "PDF conversion timed out (exceeded 60 seconds)"
        print(f"[PDF Converter] ❌ {error_msg}")
        print(f"[PDF Converter] This usually means pdflatex is stuck or asking for input")
        return {
            'success': False,
            'error': error_msg,
            'output_file': None
        }
    except Exception as e:
        error_msg = f"Unexpected error during PDF conversion: {str(e)}"
        print(f"[PDF Converter] ❌ {error_msg}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': error_msg,
            'output_file': None
        }
    finally:
        try:
            if os.path.exists(style_header_path):
                os.remove(style_header_path)
        except OSError:
            pass


def convert_markdown_to_pdf_fallback(markdown_file: str, output_pdf: str, metadata: dict = None, pandoc_path: str = 'pandoc') -> dict:
    """
    This function is no longer used - we use the simple method by default
    """
    pass


# For testing
if __name__ == "__main__":
    print("="*80)
    print("PDF Converter Module - Test Mode")
    print("="*80)
    
    # Check if Pandoc is installed
    is_installed, pandoc_path = check_pandoc_installed()
    
    if is_installed:
        print("\n✅ Pandoc is ready to use!")
        print(f"Location: {pandoc_path}")
        
        # Create a test markdown file
        test_md = "test_study_guide.md"
        test_pdf = "test_study_guide.pdf"
        
        print(f"\nCreating test markdown file: {test_md}")
        with open(test_md, 'w', encoding='utf-8') as f:
            f.write("""# Test Study Guide

## Introduction

This is a test study guide to verify PDF conversion.

## Main Concepts

### Concept 1: Learning

- Point 1
- Point 2
- Point 3

### Concept 2: Practice

1. Step one
2. Step two
3. Step three

## Summary

> This is an important note.

**Bold text** and *italic text* should render correctly.

## Code Example

```python
def hello_world():
    print("Hello, World!")
```

---

*End of test study guide*
""")
        
        print(f"Converting to PDF: {test_pdf}")
        result = convert_markdown_to_pdf(
            test_md, 
            test_pdf,
            metadata={
                'title': 'Test Study Guide',
                'author': 'AI Study Planner',
                'date': 'Today'
            }
        )
        
        if result['success']:
            print(f"\n✅ Test successful! PDF created at: {result['output_file']}")
            print("You can open it to verify the formatting.")
        else:
            print(f"\n❌ Test failed: {result['error']}")
        
        # Cleanup
        if os.path.exists(test_md):
            os.remove(test_md)
            print(f"\nCleaned up test file: {test_md}")
    else:
        print("\n❌ Please install Pandoc to use PDF conversion")
        print("Visit: https://pandoc.org/installing.html")