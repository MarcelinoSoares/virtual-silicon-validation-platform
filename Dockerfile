FROM python:3.12-slim

LABEL maintainer="Marcelino Soares de Oliveira"
LABEL description="Virtual Silicon Validation Platform"

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project source
COPY src/ ./src/
COPY tests/ ./tests/
COPY configs/ ./configs/
COPY scripts/ ./scripts/
COPY pyproject.toml .

# Install the package
RUN pip install --no-cache-dir -e .

# Create runtime directories
RUN mkdir -p reports logs

# Default environment
ENV VSVP_DATABASE_URL=sqlite:///./virtual_silicon.db
ENV VSVP_LOG_LEVEL=INFO
ENV VSVP_REPORTS_DIR=reports

EXPOSE 8000

CMD ["uvicorn", "virtual_silicon.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
