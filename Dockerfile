# Use an official Python image
FROM python:3.11-slim
# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Set proxy environment variables for the build
ENV http_proxy=http://10.48.23.75:3128
ENV https_proxy=http://10.48.23.75:3128
ENV no_proxy=localhost,127.0.0.1,0.0.0.0
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
