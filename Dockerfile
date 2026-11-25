FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY app ./app
COPY tests ./tests
COPY migrations ./migrations
COPY docs ./docs
RUN pip install --no-cache-dir pytest
CMD ["python", "-m", "pytest"]
