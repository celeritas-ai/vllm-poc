"""
Configuration management for vLLM PoC
Handles platform-specific settings and environment detection.
"""

import os
import platform
import subprocess
import sys
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PlatformConfig:
    """Platform-specific configuration."""
    name: str
    supports_cuda: bool
    supports_mps: bool  # Metal Performance Shaders (Apple Silicon)
    vllm_backend: str
    installation_method: str
    requirements_file: str
    docker_base_image: str
    additional_setup: list


class ConfigManager:
    """Manages configuration based on platform and environment."""
    
    def __init__(self):
        self.platform = self._detect_platform()
        self.config = self._get_platform_config()
        self.env_vars = self._load_environment_variables()
    
    def _detect_platform(self) -> str:
        """Detect the current platform."""
        system = platform.system().lower()
        machine = platform.machine().lower()
        
        if system == "darwin":
            if "arm" in machine or "aarch64" in machine:
                return "macos_apple_silicon"
            else:
                return "macos_intel"
        elif system == "linux":
            return "linux"
        elif system == "windows":
            return "windows"
        else:
            return "unknown"
    
    def _has_cuda(self) -> bool:
        """Check if CUDA is available."""
        try:
            result = subprocess.run(
                ["nvidia-smi"], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _has_mps(self) -> bool:
        """Check if MPS (Metal Performance Shaders) is available on macOS."""
        if not self.platform.startswith("macos"):
            return False
        try:
            import torch
            return torch.backends.mps.is_available()
        except ImportError:
            return False
    
    def _get_platform_config(self) -> PlatformConfig:
        """Get platform-specific configuration."""
        configs = {
            "macos_apple_silicon": PlatformConfig(
                name="macOS Apple Silicon",
                supports_cuda=False,
                supports_mps=True,
                vllm_backend="cpu",  # vLLM on macOS typically runs on CPU
                installation_method="pip_source",
                requirements_file="requirements-macos.txt",
                docker_base_image="python:3.11-slim",
                additional_setup=[
                    "brew install cmake",
                    "export MACOSX_DEPLOYMENT_TARGET=11.0",
                    "pip install torch torchvision torchaudio"
                ]
            ),
            "macos_intel": PlatformConfig(
                name="macOS Intel",
                supports_cuda=False,
                supports_mps=False,
                vllm_backend="cpu",
                installation_method="pip_source",
                requirements_file="requirements-macos.txt",
                docker_base_image="python:3.11-slim",
                additional_setup=[
                    "brew install cmake",
                    "pip install torch torchvision torchaudio"
                ]
            ),
            "linux": PlatformConfig(
                name="Linux",
                supports_cuda=self._has_cuda(),
                supports_mps=False,
                vllm_backend="cuda" if self._has_cuda() else "cpu",
                installation_method="pip",
                requirements_file="requirements.txt",
                docker_base_image="nvidia/cuda:12.1-devel-ubuntu22.04",
                additional_setup=[]
            ),
            "windows": PlatformConfig(
                name="Windows",
                supports_cuda=self._has_cuda(),
                supports_mps=False,
                vllm_backend="cuda" if self._has_cuda() else "cpu",
                installation_method="pip",
                requirements_file="requirements-windows.txt",
                docker_base_image="mcr.microsoft.com/windows/servercore:ltsc2022",
                additional_setup=[
                    "Install Visual Studio Build Tools",
                    "Install CUDA Toolkit if GPU acceleration needed"
                ]
            )
        }
        
        return configs.get(self.platform, configs["linux"])
    
    def _load_environment_variables(self) -> Dict[str, Any]:
        """Load environment variables with defaults."""
        return {
            "MODEL_NAME": os.getenv("MODEL_NAME", self._get_default_model()),
            "HOST": os.getenv("HOST", "0.0.0.0"),
            "PORT": int(os.getenv("PORT", "8000")),
            "MAX_MODEL_LEN": int(os.getenv("MAX_MODEL_LEN", "2048")),
            "GPU_MEMORY_UTILIZATION": float(os.getenv("GPU_MEMORY_UTILIZATION", "0.9")),
            "TENSOR_PARALLEL_SIZE": int(os.getenv("TENSOR_PARALLEL_SIZE", "1")),
            "TRUST_REMOTE_CODE": os.getenv("TRUST_REMOTE_CODE", "true").lower() == "true",
            "ENFORCE_EAGER": os.getenv("ENFORCE_EAGER", "false").lower() == "true",
            "DISABLE_CUSTOM_ALL_REDUCE": os.getenv("DISABLE_CUSTOM_ALL_REDUCE", "false").lower() == "true",
        }
    
    def _get_default_model(self) -> str:
        """Get default model based on platform capabilities."""
        if self.config.supports_cuda:
            return "microsoft/DialoGPT-medium"
        else:
            # Smaller model for CPU/non-CUDA environments
            return "microsoft/DialoGPT-small"
    
    def get_vllm_args(self) -> Dict[str, Any]:
        """Get vLLM engine arguments based on platform."""
        base_args = {
            "model": self.env_vars["MODEL_NAME"],
            "tensor_parallel_size": self.env_vars["TENSOR_PARALLEL_SIZE"],
            "max_model_len": self.env_vars["MAX_MODEL_LEN"],
            "trust_remote_code": self.env_vars["TRUST_REMOTE_CODE"],
        }
        
        if self.config.supports_cuda:
            base_args.update({
                "gpu_memory_utilization": self.env_vars["GPU_MEMORY_UTILIZATION"],
                "dtype": "auto",
            })
        else:
            # CPU-specific optimizations
            base_args.update({
                "enforce_eager": True,
                "disable_custom_all_reduce": True,
            })
        
        # macOS-specific settings
        if self.platform.startswith("macos"):
            base_args.update({
                "enforce_eager": True,
                "disable_custom_all_reduce": True,
                "max_num_seqs": 16,  # Lower for CPU
            })
        
        return base_args
    
    def get_installation_command(self) -> str:
        """Get the appropriate installation command for the platform."""
        if self.platform.startswith("macos"):
            return """
# macOS Installation (Apple Silicon/Intel)
pip install --upgrade pip
pip install torch torchvision torchaudio
pip install vllm --no-build-isolation
# If above fails, try: pip install vllm --no-deps
"""
        elif self.platform == "linux" and self.config.supports_cuda:
            return """
# Linux with CUDA Installation
pip install --upgrade pip
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install vllm
"""
        else:
            return """
# CPU-only Installation
pip install --upgrade pip
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install vllm
"""
    
    def validate_environment(self) -> Dict[str, Any]:
        """Validate the current environment setup."""
        validation = {
            "platform": self.platform,
            "python_version": sys.version,
            "torch_available": False,
            "cuda_available": False,
            "mps_available": False,
            "vllm_available": False,
            "recommendations": []
        }
        
        try:
            import torch
            validation["torch_available"] = True
            validation["cuda_available"] = torch.cuda.is_available()
            if hasattr(torch.backends, 'mps'):
                validation["mps_available"] = torch.backends.mps.is_available()
        except ImportError:
            validation["recommendations"].append("Install PyTorch")
        
        try:
            import vllm
            validation["vllm_available"] = True
        except ImportError:
            validation["recommendations"].append("Install vLLM")
        
        # Platform-specific recommendations
        if self.platform.startswith("macos") and not validation["torch_available"]:
            validation["recommendations"].append("Install PyTorch for macOS")
        
        if self.config.supports_cuda and not validation["cuda_available"]:
            validation["recommendations"].append("CUDA detected but PyTorch CUDA not available")
        
        return validation
    
    def print_platform_info(self):
        """Print platform and configuration information."""
        print(f"🖥️  Platform: {self.config.name}")
        print(f"🔧 Backend: {self.config.vllm_backend}")
        print(f"🎯 CUDA Support: {'✅' if self.config.supports_cuda else '❌'}")
        print(f"🍎 MPS Support: {'✅' if self.config.supports_mps else '❌'}")
        print(f"📦 Requirements: {self.config.requirements_file}")
        print(f"🐳 Docker Base: {self.config.docker_base_image}")
        
        if self.config.additional_setup:
            print("🛠️  Additional Setup Required:")
            for step in self.config.additional_setup:
                print(f"   - {step}")


# Global config instance
config = ConfigManager()


def get_config() -> ConfigManager:
    """Get the global configuration instance."""
    return config


if __name__ == "__main__":
    config = ConfigManager()
    config.print_platform_info()
    
    print("\n📋 Environment Validation:")
    validation = config.validate_environment()
    for key, value in validation.items():
        if key != "recommendations":
            print(f"   {key}: {value}")
    
    if validation["recommendations"]:
        print("\n💡 Recommendations:")
        for rec in validation["recommendations"]:
            print(f"   - {rec}")
    
    print(f"\n🚀 Installation Command:")
    print(config.get_installation_command())