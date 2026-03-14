FROM python:3.12-slim

# Injected by GitHub Actions build — bakes the source commit into the image.
# Visible at /integrity on the running server.
ARG GIT_SHA=unknown
ENV GIT_SHA=${GIT_SHA}

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

# counts.json lives on a mounted volume so counts survive restarts
VOLUME ["/app/data"]
ENV COUNTS_FILE=/app/data/counts.json

EXPOSE 8000

# --no-access-log is critical: prevents uvicorn from logging IP addresses
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
