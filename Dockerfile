FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY quickdraw/ quickdraw/
COPY SOUL.md config.example.yaml ./

RUN pip install --no-cache-dir -e '.[teams,llm]' temporalio

EXPOSE 5000 3978

CMD ["python", "-m", "quickdraw", "run", "--config", "/app/config.example.yaml"]
