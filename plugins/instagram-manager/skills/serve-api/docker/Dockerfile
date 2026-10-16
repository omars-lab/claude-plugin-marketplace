# The saved places data API (serve-api). Built from the plugin folder:
#   docker build -f skills/serve-api/docker/Dockerfile <plugin folder>
# compose.yaml next to this file mounts the data folder at /data and the plugin's code over /plugin,
# so code edits reload without a rebuild.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 INSTAGRAM_HOME=/data
COPY skills/serve-api/docker/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY shared /plugin/shared
COPY skills /plugin/skills
WORKDIR /plugin

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"
CMD ["uvicorn", "api:app", "--app-dir", "/plugin/skills/serve-api/scripts", "--host", "0.0.0.0", "--port", "8000"]
