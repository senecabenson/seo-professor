FROM node:20-slim

# Install Python and WeasyPrint system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN pip3 install --no-cache-dir -e . --break-system-packages
