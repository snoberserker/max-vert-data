FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
COPY run.sh /work/run.sh
RUN chmod +x /work/run.sh
ENTRYPOINT ["/work/run.sh"]
