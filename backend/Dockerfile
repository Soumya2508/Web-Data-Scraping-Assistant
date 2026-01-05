FROM python:3.12-slim

WORKDIR /app

# System deps for lxml/pandas builds (kept minimal)
RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app

ENV PYTHONUNBUFFERED=1
ENV WDSP_EXPORTS_DIR=/app/exports

EXPOSE 8000

CMD ["python","-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
