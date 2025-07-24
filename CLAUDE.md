# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a vLLM Proof of Concept project that demonstrates end-to-end workflow for:
- Standing up vLLM locally
- Containerizing with Docker
- Automating builds and deployments using GitHub Actions
- Production-grade considerations (GPU scheduling, monitoring, hot-swappable LoRA adapters)

## Prerequisites & Environment

### Hardware & OS
- Local machine with NVIDIA GPU (ideally A100/A6000 or comparable)
- Ubuntu 22.04 LTS (or equivalent) with NVIDIA drivers and Docker installed

### Software Requirements
- Docker Engine (>= 24.x) and NVIDIA Container Toolkit for GPU support
- Python 3.11+ with vLLM installed (`pip install vllm`)
- Git and GitHub account with repo access
- AWS CLI configured with credentials and permissions to push images to ECR and deploy to ECS/EKS

## Development Workflow

This project follows an end-to-end containerized deployment workflow:
1. Local vLLM development and testing
2. Docker containerization with GPU support
3. GitHub Actions CI/CD for automated builds
4. Production deployment with monitoring and LoRA adapter support

## Architecture Notes

- GPU scheduling and resource management for production workloads
- Hot-swappable LoRA adapters for model customization
- Monitoring and observability integration
- Container orchestration ready for ECS/EKS deployment