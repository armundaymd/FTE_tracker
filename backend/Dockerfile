FROM python:3.12-slim

WORKDIR /app

# Install dependencies in a separate layer so rebuilds skip this step
# when only source code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source. In docker-compose development mode this layer is shadowed
# by the bind-mount volume, so changes on the host are reflected immediately.
COPY . .

EXPOSE 8000

# Production default. docker-compose overrides this with --reload.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
