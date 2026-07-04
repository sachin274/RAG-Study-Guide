# RAG Study Guide Generator

An AI-powered study guide generator that turns any PDF into a focused, topic-specific
study guide. Upload a document, tell it what topics you want to study, and it uses a
Retrieval-Augmented Generation (RAG) pipeline plus Google Gemini to produce a
well-structured, styled PDF study guide covering only the material relevant to your
topics.

## **Project Demo Video Link** : https://drive.google.com/file/d/1xSLmSSPKotZMGVddONu43vSbryvNQrwm/view?usp=drive_link

## How It Works

1. **Upload** — a PDF is uploaded through the web UI along with a list of topics to study.
2. **Extract** — text is extracted from the PDF page by page ([pdf_extracter.py](pdf_extracter.py)).
3. **Chunk** — the extracted text is split into overlapping ~1000-character chunks
   ([text_chunks.py](text_chunks.py)).
4. **Embed** — each chunk is embedded locally using a HuggingFace sentence-transformer
   model and stored in a FAISS vector index ([embedding.py](embedding.py)). No API calls
   or cost for this step.
5. **Retrieve** — each requested topic is searched against the vector store separately
   (so a multi-topic request doesn't drown out material that's only relevant to one
   topic), ranked by similarity, and capped to keep the result focused. Narrow or
   single-word topics fall back to the best-ranked matches available so they still
   return useful content ([main_rag.py](main_rag.py)).
6. **Generate** — the retrieved excerpts are sent to Google Gemini with a prompt
   instructing it to produce a focused, well-organized study guide covering only the
   relevant material ([gemini_generator.py](gemini_generator.py)).
7. **Render** — the generated Markdown is converted to a styled PDF (custom CSS, table
   of contents, formatted tables/headings) using Pandoc + wkhtmltopdf
   ([pdf_converter.py](pdf_converter.py)).
8. **Download** — the finished PDF is served back to the browser for download.

## Tech Stack

- **Backend:** Flask (Python)
- **PDF text extraction:** pypdf
- **Text chunking:** LangChain (`RecursiveCharacterTextSplitter`)
- **Embeddings:** HuggingFace `sentence-transformers/all-MiniLM-L6-v2` (local, free, no API key)
- **Vector store:** FAISS
- **Generation:** Google Gemini (`gemini-2.5-flash`)
- **Markdown → PDF:** Pandoc with the wkhtmltopdf engine
- **Frontend:** Static HTML/CSS/JS served by Flask (no build step)

## Prerequisites

- Python 3.11+
- [Pandoc](https://pandoc.org/installing.html) installed and on your `PATH`
- [wkhtmltopdf](https://wkhtmltopdf.org/downloads.html) installed and on your `PATH`
- A [Google AI Studio / Gemini API key](https://aistudio.google.com/apikey)

## Setup

1. Clone the repo and create a virtual environment:

   ```bash
   python -m venv venv
   venv\Scripts\activate      # Windows
   source venv/bin/activate   # macOS/Linux
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root with your Gemini API key:

   ```
   GOOGLE_API_KEY=your_api_key_here
   ```

4. Run the app:

   ```bash
   python app.py
   ```

5. Open [http://localhost:5000](http://localhost:5000) in your browser.

## API Endpoints

| Method | Endpoint                   | Description                                                                                       |
| ------ | -------------------------- | ------------------------------------------------------------------------------------------------- |
| `GET`  | `/`                        | Serves the web UI                                                                                 |
| `POST` | `/api/generate`            | Accepts a `file` (PDF) and `topics` (form fields), runs the full pipeline, returns a download URL |
| `GET`  | `/api/download/<filename>` | Downloads a generated study guide                                                                 |
| `GET`  | `/api/health`              | Health check                                                                                      |

## Project Structure

```
app.py                 Flask app, routes, request orchestration
main_rag.py             RAG pipeline: extraction -> chunking -> embedding -> retrieval
pdf_extracter.py         PDF -> raw text
text_chunks.py           Raw text -> chunks
embedding.py             Chunks -> FAISS vector store (HuggingFace embeddings)
gemini_generator.py       Retrieved chunks -> Gemini-generated Markdown study guide
pdf_converter.py          Markdown -> styled PDF (Pandoc + wkhtmltopdf)
templates/index.html      Frontend UI
static/styles.css         Frontend styling
uploads/                  Uploaded source PDFs (gitignored)
extracted_text/           Extracted raw text per upload (gitignored)
faiss_stores/             Per-upload FAISS vector stores (gitignored)
outputs/                  Generated study guide PDFs (gitignored)
```

## Deployment (Render)

The app ships with a `Dockerfile` (installs Pandoc + the patched-Qt wkhtmltopdf
build, pre-downloads the embedding model, and serves via Gunicorn) and a
`render.yaml` Blueprint.

1. Push this repo to GitHub.
2. In the Render dashboard: **New > Blueprint**, connect the repo. Render will read
   `render.yaml` and create the web service automatically (Docker runtime, free plan,
   health check on `/api/health`).
   - Alternatively: **New > Web Service**, connect the repo, and choose **Docker** as
     the runtime manually.
3. Set the `GOOGLE_API_KEY` environment variable in the service's **Environment** tab
   (the Blueprint will prompt for it since it's marked as a secret, not committed).
4. Deploy. The first build takes a while (installing wkhtmltopdf + torch +
   sentence-transformers and pre-baking the embedding model into the image).
5. Once live, Render gives you a URL like `https://rag-study-guide.onrender.com` —
   the frontend now uses relative API paths, so it works there without any code changes.

**Caveats to know about before relying on this in production:**

- **Ephemeral, single-instance storage.** `uploads/`, `extracted_text/`,
  `faiss_stores/`, and `outputs/` are written to local disk. Render's default web
  service disk is ephemeral (wiped on redeploy/restart) and not shared across
  instances. This is fine as long as you run exactly **one** instance (no
  autoscaling) — each request's upload → generate → download happens within that
  same instance — but don't scale this service horizontally without adding real
  object storage (e.g. S3) and a shared vector DB.
- **Memory.** Render's free tier (512MB RAM) can be tight with `torch` +
  `sentence-transformers` loaded alongside Flask/Gunicorn. If you see the service
  crash or 502 under load, upgrade to a paid instance type with more RAM.
- **Request timeout.** Generation can take 30-90+ seconds for larger documents.
  Gunicorn is configured with a 180s timeout; if you switch to a different platform,
  make sure its own request/proxy timeout is at least that long too.

## Notes

- `uploads/`, `extracted_text/`, `faiss_stores/`, and `outputs/` are runtime data and are
  gitignored — nothing is cleaned up automatically, so these will grow over time with
  local usage.
- The Flask dev server (`app.run(debug=True, ...)`) is for local development only, not
  production deployment.
- Each request creates its own FAISS vector store rather than reusing one across
  requests, so re-uploading the same document re-embeds it from scratch.
