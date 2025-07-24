# vLLM Proof of Concept

A containerized vLLM inference server with GPU support, monitoring, and CI/CD automation.

## Quick Start

### Prerequisites

**Platform Support:**
- ✅ **macOS** (Apple Silicon/Intel) - CPU inference
- ✅ **Linux** - GPU (CUDA) or CPU inference  
- ✅ **Windows** - GPU (CUDA) or CPU inference

**System Requirements:**
- Python 3.11+
- For GPU acceleration: NVIDIA GPU with CUDA support
- For Docker: Docker with NVIDIA Container Toolkit (Linux only)

### Automated Setup

**Option 1: Automated Platform Setup** (Recommended)
```bash
git clone <your-repo>
cd "vLLM PoC"
python3 scripts/setup_platform.py
```

This script will:
- Detect your platform (macOS/Linux/Windows)
- Create virtual environment
- Install platform-specific dependencies
- Configure optimal settings
- Create platform-specific run scripts

**Option 2: Manual Setup**
```bash
git clone <your-repo>
cd "vLLM PoC"
python3 -m venv venv

# Activate virtual environment
# macOS/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Install dependencies based on your platform
pip install -r requirements-macos.txt     # macOS
pip install -r requirements.txt          # Linux
pip install -r requirements-windows.txt  # Windows
```

### Running the Server

**After setup, start the server:**
```bash
# Use generated script
./run.sh        # macOS/Linux
run.bat         # Windows

# Or manually
source venv/bin/activate && python app.py
```

**Test the API:**
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hello!"}]}'
```

## Development Commands

### Local Development
```bash
# Check platform configuration
python3 config.py

# Run setup
python3 scripts/setup_platform.py

# Start server
python app.py

# Run tests
python -m pytest tests/
```

### Docker (Linux with NVIDIA GPU)
```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f vllm-server

# Stop services
docker-compose down

# Run with monitoring stack
docker-compose --profile monitoring up -d

# Build image
docker build -t vllm-poc .
```

## API Endpoints

- **Health Check**: `GET /health`
- **Chat Completions**: `POST /v1/chat/completions`
- **List Models**: `GET /models`

## Configuration

### Platform-Specific Settings

The application automatically detects your platform and configures optimal settings:

**macOS (Apple Silicon/Intel):**
- CPU-only inference (vLLM GPU support limited on macOS)
- Optimized for Metal Performance Shaders when available
- Smaller default models for better performance

**Linux:**
- CUDA GPU acceleration when available
- Full vLLM feature support
- Docker containerization with GPU passthrough

**Windows:**
- CUDA GPU acceleration when available
- Windows-specific dependency handling

### Environment Variables

See `.env.example` for all options:
- `MODEL_NAME`: HuggingFace model to load (auto-selected by platform)
- `CUDA_VISIBLE_DEVICES`: GPU device selection (Linux/Windows)
- `PORT`: Server port (default: 8000)
- `MAX_MODEL_LEN`: Maximum sequence length
- `GPU_MEMORY_UTILIZATION`: GPU memory usage (0.0-1.0)

## Monitoring

Optional monitoring stack with Prometheus and Grafana:
```bash
docker-compose --profile monitoring up -d
```
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin)

## AWS Deployment

### Quick Test Deployment (5 minutes)

**Fastest way to test on AWS:**
```bash
# Ensure AWS CLI is configured
aws configure

# Quick deploy (launches single EC2 instance)
./scripts/quick_aws_deploy.sh
```

This will:
- Launch a GPU-enabled EC2 instance (g4dn.xlarge)
- Install Docker and dependencies
- Run the vLLM PoC server
- Provide public URL for testing

**Access your deployment:**
- Health check: `http://YOUR_IP:8000/health`
- API docs: `http://YOUR_IP:8000/docs`
- Chat API: `http://YOUR_IP:8000/v1/chat/completions`

### Production Deployment

For production, use the full ECS deployment:
```bash
./scripts/deploy_aws.sh
```

The project includes:
- ECS cluster with GPU support
- ECR container registry
- Load balancer configuration
- Auto-scaling and health checks
- GitHub Actions CI/CD pipeline

## Architecture

- **FastAPI**: Web framework with OpenAI-compatible API
- **vLLM**: High-performance inference engine
- **Docker**: Containerization with GPU support
- **Prometheus**: Metrics collection
- **GitHub Actions**: CI/CD automation