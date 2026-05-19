FROM python:3.11-slim as base
FROM base as builder
RUN mkdir /install
WORKDIR /install
COPY requirement.txt /requirement.txt
RUN pip install --prefix=/install -r /requirement.txt
FROM base
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /install /usr/local
RUN mkdir -p /app/agent
COPY agent /app/agent
COPY ostorlab.yaml /app/agent/ostorlab.yaml
ENV PYTHONPATH=/app
WORKDIR /app/agent
CMD ["python3.11", "/app/agent/agent.py"]
