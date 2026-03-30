# Install openapi-generator-cli in a builder stage and run generate.sh.
# NPM package requires Java; final image stays Python-only.
FROM node:20-slim AS generator
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jre-headless ca-certificates && rm -rf /var/lib/apt/lists/*
RUN npm install -g @openapitools/openapi-generator-cli
WORKDIR /work
COPY openapi/ openapi/
COPY app/ app/
COPY generate.sh ./
RUN chmod +x generate.sh && ./generate.sh

FROM python:3.11-slim
WORKDIR /app

ENV PYTHONPATH=/app:/app/app:/app/app/generated

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY --from=generator /work/app/generated ./app/generated

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
