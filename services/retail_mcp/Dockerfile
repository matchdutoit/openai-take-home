FROM python:3.11-slim

WORKDIR /app

COPY services/retail_mcp/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY . /app

EXPOSE 8081

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8081/health').status == 200 else 1)"

CMD ["python", "-m", "services.retail_mcp.app.server"]
