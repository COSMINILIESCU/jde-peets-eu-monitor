# Container for the collection/export pipeline (tests and portable runs).
# Note: the AI analysis step uses the Claude Code CLI on the host by default;
# in the container, run with --no-analyze, or set analysis.engine=anthropic-api
# and provide ANTHROPIC_API_KEY.
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY config/ config/
COPY sources/ sources/
COPY src/ src/
COPY scripts/ scripts/
COPY docs/ docs/
COPY tests/ tests/

ENV PYTHONUNBUFFERED=1
CMD ["python", "scripts/run_weekly.py", "--no-analyze", "--no-publish"]
