FROM python:3.11-slim as base
FROM base as builder
RUN pip install uv
RUN mkdir /install
WORKDIR /install
COPY requirement.txt /requirement.txt
RUN uv pip install --prefix=/install --system -r /requirement.txt
FROM base
COPY --from=builder /install /usr/local
RUN mkdir -p /app/agent
COPY agent /app/agent
COPY ostorlab.yaml /app/agent/ostorlab.yaml
WORKDIR /app/agent
CMD ["python3.11", "/app/agent/agent.py"]
