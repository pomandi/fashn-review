FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy app source
COPY app ./app
COPY core ./core
COPY wsgi.py entrypoint.sh ./

# Seed data — moved to /app/data_seed so a persistent volume mounted on /app/data
# can be hydrated on first start without permanently shadowing the seed files.
COPY data ./data_seed

RUN chmod +x entrypoint.sh && mkdir -p /app/data /app/output /app/logs

EXPOSE 5000

CMD ["./entrypoint.sh"]
