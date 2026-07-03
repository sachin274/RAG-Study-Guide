# RAG Study Guide Generator - production image
FROM python:3.11-slim

# System dependencies:
# - pandoc: markdown -> PDF conversion driver
# - wkhtmltopdf (patched-Qt static build): headless HTML->PDF rendering engine
#   used by pandoc. The plain Debian "wkhtmltopdf" apt package is NOT the
#   patched-Qt build and will not render headless, so it's installed from the
#   official packaged release instead.
RUN apt-get update && apt-get install -y --no-install-recommends \
        pandoc \
        curl \
        fontconfig \
        libxrender1 \
        libxext6 \
        libjpeg62-turbo \
        xfonts-75dpi \
        xfonts-base \
    && curl -fsSL -o /tmp/wkhtmltox.deb \
        https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.bookworm_amd64.deb \
    && apt-get install -y --no-install-recommends /tmp/wkhtmltox.deb \
    && rm /tmp/wkhtmltox.deb \
    && apt-get purge -y curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the embedding model into the image so the first real request
# isn't slowed down (or timed out) by a runtime download.
RUN python -c "from langchain_community.embeddings import HuggingFaceEmbeddings; \
    HuggingFaceEmbeddings(model_name='sentence-transformers/all-MiniLM-L6-v2')"

COPY . .

# Runtime data directories (uploads/outputs/etc. are created by app.py too,
# but declaring them here avoids a first-request race under multiple workers)
RUN mkdir -p uploads outputs extracted_text faiss_stores

# Render (and most PaaS) inject $PORT at runtime; default kept for local `docker run`
ENV PORT=5000
EXPOSE 5000

# gthread workers share one process (and one loaded embedding model) across
# threads instead of forking it per worker, and the long timeout accounts for
# Gemini generation + PDF conversion, which can take 30-90+ seconds.
CMD gunicorn app:app \
    --bind 0.0.0.0:$PORT \
    --workers 1 \
    --worker-class gthread \
    --threads 4 \
    --timeout 180
