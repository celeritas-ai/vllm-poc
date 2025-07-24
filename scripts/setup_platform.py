#!/usr/bin/env python3
"""
Platform setup script for vLLM PoC
Automatically detects platform and sets up the appropriate environment.
"""

import sys
import subprocess
import os
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import ConfigManager


def run_command(command: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    print(f"🔄 Running: {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    
    if check and result.returncode != 0:
        print(f"❌ Command failed: {command}")
        print(f"   Error: {result.stderr}")
        sys.exit(1)
    
    if result.stdout:
        print(f"   Output: {result.stdout.strip()}")
    
    return result


def setup_virtual_environment():
    """Set up Python virtual environment."""
    if not os.path.exists("venv"):
        print("📦 Creating virtual environment...")
        run_command("python3 -m venv venv")
    else:
        print("✅ Virtual environment already exists")


def install_requirements(config_manager: ConfigManager):
    """Install platform-specific requirements."""
    requirements_file = config_manager.config.requirements_file
    
    if not os.path.exists(requirements_file):
        print(f"⚠️  Requirements file {requirements_file} not found, using default")
        requirements_file = "requirements-simple.txt"
    
    print(f"📦 Installing requirements from {requirements_file}...")
    
    # Activate virtual environment and install requirements
    if sys.platform == "win32":
        activate_cmd = "venv\\Scripts\\activate"
    else:
        activate_cmd = "source venv/bin/activate"
    
    install_cmd = f"{activate_cmd} && pip install --upgrade pip && pip install -r {requirements_file}"
    
    try:
        run_command(install_cmd)
        print("✅ Requirements installed successfully")
    except SystemExit:
        print("⚠️  Some packages failed to install, trying simplified installation...")
        
        # Try installing basic requirements first
        basic_cmd = f"{activate_cmd} && pip install fastapi uvicorn pydantic"
        run_command(basic_cmd)
        
        # Try vLLM with specific flags for macOS
        if config_manager.platform.startswith("macos"):
            vllm_cmd = f"{activate_cmd} && pip install vllm --no-build-isolation || pip install vllm --no-deps"
            run_command(vllm_cmd, check=False)


def setup_platform_specific(config_manager: ConfigManager):
    """Run platform-specific setup commands."""
    print(f"🛠️  Running platform-specific setup for {config_manager.config.name}...")
    
    for command in config_manager.config.additional_setup:
        print(f"   📋 {command}")
        if command.startswith("brew"):
            # Check if Homebrew is installed on macOS
            if config_manager.platform.startswith("macos"):
                result = run_command("which brew", check=False)
                if result.returncode != 0:
                    print("   ⚠️  Homebrew not found. Please install Homebrew first:")
                    print("   /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
                    continue
        
        # Run the command (non-critical)
        run_command(command, check=False)


def validate_installation(config_manager: ConfigManager):
    """Validate the installation."""
    print("🔍 Validating installation...")
    
    validation = config_manager.validate_environment()
    
    print(f"   Platform: {validation['platform']}")
    print(f"   Python: {validation['python_version']}")
    print(f"   PyTorch: {'✅' if validation['torch_available'] else '❌'}")
    print(f"   CUDA: {'✅' if validation['cuda_available'] else '❌'}")
    print(f"   MPS: {'✅' if validation['mps_available'] else '❌'}")
    print(f"   vLLM: {'✅' if validation['vllm_available'] else '❌'}")
    
    if validation["recommendations"]:
        print("💡 Recommendations:")
        for rec in validation["recommendations"]:
            print(f"   - {rec}")
    
    return validation


def create_run_script(config_manager: ConfigManager):
    """Create platform-specific run script."""
    if sys.platform == "win32":
        script_name = "run.bat"
        script_content = f"""@echo off
call venv\\Scripts\\activate
echo 🚀 Starting vLLM PoC Server...
python app.py
pause
"""
    else:
        script_name = "run.sh"
        script_content = f"""#!/bin/bash
source venv/bin/activate
echo "🚀 Starting vLLM PoC Server..."
python app.py
"""
    
    with open(script_name, "w") as f:
        f.write(script_content)
    
    if not sys.platform == "win32":
        os.chmod(script_name, 0o755)
    
    print(f"✅ Created run script: {script_name}")


def main():
    """Main setup function."""
    print("🚀 vLLM PoC Platform Setup")
    print("=" * 50)
    
    # Initialize configuration
    config_manager = ConfigManager()
    config_manager.print_platform_info()
    
    print("\n📋 Setup Steps:")
    
    # Step 1: Virtual environment
    setup_virtual_environment()
    
    # Step 2: Platform-specific setup
    setup_platform_specific(config_manager)
    
    # Step 3: Install requirements
    install_requirements(config_manager)
    
    # Step 4: Validate installation
    validation = validate_installation(config_manager)
    
    # Step 5: Create run script
    create_run_script(config_manager)
    
    # Final instructions
    print("\n🎉 Setup Complete!")
    print("=" * 50)
    
    if validation["vllm_available"]:
        print("✅ vLLM is available - you can run the full server")
    else:
        print("⚠️  vLLM not available - server will run in demo mode")
    
    print("\n🚀 To start the server:")
    if sys.platform == "win32":
        print("   run.bat")
    else:
        print("   ./run.sh")
    
    print("\n📡 Or manually:")
    if sys.platform == "win32":
        print("   venv\\Scripts\\activate")
    else:
        print("   source venv/bin/activate")
    print("   python app.py")
    
    print(f"\n🌐 Server will be available at: http://localhost:{config_manager.env_vars['PORT']}")
    print(f"📚 API documentation: http://localhost:{config_manager.env_vars['PORT']}/docs")


if __name__ == "__main__":
    main()