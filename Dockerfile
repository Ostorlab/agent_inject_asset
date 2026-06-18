FROM python:3.14-slim as base
FROM base as builder
RUN pip install uv
RUN mkdir /install
WORKDIR /install
COPY requirement.txt /requirement.txt
RUN uv pip install --prefix=/install -r /requirement.txt
FROM base
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /install /usr/local
RUN mkdir -p /app/agent
COPY agent /app/agent
COPY ostorlab.yaml /app/agent/ostorlab.yaml
WORKDIR /app
CMD ["python", "-m", "agent.agent_inject_asset"]
