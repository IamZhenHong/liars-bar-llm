# Use an official Python image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose the port your app runs on
EXPOSE 8000

# Run the app with uvicorn
CMD ["uvicorn", "game_server:app", "--host", "0.0.0.0", "--port", "8000"]
