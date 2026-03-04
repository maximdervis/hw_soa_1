FROM openapitools/openapi-generator-cli AS generator
WORKDIR /app
COPY openapi /app/openapi
COPY generate.sh /app/generate.sh
RUN chmod +x generate.sh && ./generate.sh

FROM python:3.11-slim
WORKDIR /app
ENV PYTHONPATH=/app:/app/app
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY --from=generator /app/app/generated /app/app/generated

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
