# Minimal HTTP MCP image for asd-ste100-checker.
# Runtime requires STE100_MCP_TOKEN. Text/payload tools work; host filesystem /
# git-based tools (ste_check_file relative paths, ste_check_changed_files) are
# not the intended Docker story.
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY ste100 ./ste100

RUN pip install --no-cache-dir . \
    && python -m spacy download en_core_web_sm \
    && rm -rf /root/.cache/pip

EXPOSE 8765

# STE100_MCP_TOKEN must be set at runtime (Bearer auth for HTTP).
CMD ["python", "-m", "ste100", "serve", "--transport", "http", "--host", "0.0.0.0", "--port", "8765"]
