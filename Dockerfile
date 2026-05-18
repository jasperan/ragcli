FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy the source code
COPY . .

# Install the package and console script
RUN pip install --no-cache-dir -e .

# Expose FastAPI port
EXPOSE 8000

# Default command: launch API server
CMD ["ragcli", "api", "--host", "0.0.0.0", "--port", "8000"]
