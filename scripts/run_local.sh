#!/bin/bash

# vLLM PoC Local Development Script
set -e

echo "🚀 Starting vLLM PoC Local Development Environment"

# Check if .env file exists, if not copy from example
if [ ! -f .env ]; then
    echo "📋 Creating .env file from example..."
    cp .env.example .env
    echo "✅ Please edit .env file with your configuration"
fi

# Check if NVIDIA Docker runtime is available
if ! docker info | grep -q nvidia; then
    echo "⚠️  NVIDIA Docker runtime not detected. GPU support may not work."
    echo "   Please install NVIDIA Container Toolkit for GPU support."
fi

# Function to check if container is healthy
check_health() {
    local container_name=$1
    local max_attempts=30
    local attempt=1
    
    echo "🔍 Checking health of $container_name..."
    
    while [ $attempt -le $max_attempts ]; do
        if docker exec $container_name curl -f http://localhost:8000/health > /dev/null 2>&1; then
            echo "✅ $container_name is healthy!"
            return 0
        fi
        
        echo "⏳ Attempt $attempt/$max_attempts - waiting for $container_name to be ready..."
        sleep 5
        attempt=$((attempt + 1))
    done
    
    echo "❌ $container_name failed to become healthy after $max_attempts attempts"
    return 1
}

# Build and start the services
echo "🔨 Building Docker image..."
docker-compose build

echo "🎯 Starting vLLM server..."
docker-compose up -d vllm-server

# Wait for service to be healthy
if check_health "vllm-poc"; then
    echo ""
    echo "🎉 vLLM PoC is running successfully!"
    echo ""
    echo "📡 Available endpoints:"
    echo "   Health Check: http://localhost:8000/health"
    echo "   Chat API:     http://localhost:8000/v1/chat/completions"
    echo "   Models:       http://localhost:8000/models"
    echo ""
    echo "🔧 Development commands:"
    echo "   View logs:    docker-compose logs -f vllm-server"
    echo "   Stop:         docker-compose down"
    echo "   Restart:      docker-compose restart vllm-server"
    echo ""
    echo "💡 Test the API with:"
    echo '   curl -X POST http://localhost:8000/v1/chat/completions \'
    echo '     -H "Content-Type: application/json" \'
    echo '     -d '"'"'{"messages":[{"role":"user","content":"Hello!"}]}'"'"
else
    echo "❌ Failed to start vLLM PoC"
    echo "📋 Checking logs..."
    docker-compose logs vllm-server
    exit 1
fi