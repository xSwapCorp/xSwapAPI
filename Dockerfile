FROM python:3.10-alpine
WORKDIR /backend

COPY scripts/ scripts/
# COPY .env .
COPY requirements.txt .
EXPOSE 5001

RUN pip install --no-cache-dir -r requirements.txt
