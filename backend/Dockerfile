FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY . .

# Seed assets (design_system/) ship inside the image so a fresh named volume
# gets them on first boot. data/output is generated at runtime.
RUN mkdir -p data/output \
    && chown -R 1000:1000 /app/data

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
