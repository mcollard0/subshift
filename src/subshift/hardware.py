"""
Hardware detection and system configuration for optimal Whisper performance.

This module detects available hardware (CPU, GPU, CUDA) and provides
configuration recommendations for local Whisper processing.
"""
import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .logging import get_logger


@dataclass
class GPUInfo:
    """Information about detected GPU hardware."""
    name: str
    memory_mb: int
    driver_version: str
    cuda_version: Optional[str] = None
    compute_capability: Optional[str] = None


@dataclass
class SystemCapabilities:
    """System hardware capabilities for AI processing."""
    cpu_cores: int
    cpu_threads: int
    cpu_name: str
    total_ram_gb: float
    available_ram_gb: float
    
    # GPU information
    has_nvidia_gpu: bool = False
    has_cuda: bool = False
    gpus: List[GPUInfo] = None
    
    # Compute capabilities
    torch_available: bool = False
    torch_cuda_available: bool = False
    recommended_device: str = "cpu"
    
    # Whisper model recommendations
    recommended_models: List[str] = None
    max_recommended_model: str = "base"


class HardwareDetector:
    """Detects and analyzes system hardware for optimal Whisper configuration."""
    
    def __init__(self):
        self.logger = get_logger()
        self._capabilities = None
    
    def detect_system_capabilities(self) -> SystemCapabilities:
        """
        Comprehensively detect system hardware and capabilities.
        
        Returns:
            SystemCapabilities with all detected information
        """
        if self._capabilities is not None:
            return self._capabilities
            
        self.logger.info("🔍 Detecting system hardware capabilities...")
        
        capabilities = SystemCapabilities(
            cpu_cores=0,
            cpu_threads=0, 
            cpu_name="Unknown",
            total_ram_gb=0.0,
            available_ram_gb=0.0
        )
        
        # Detect CPU information
        self._detect_cpu_info(capabilities)
        
        # Detect memory information
        self._detect_memory_info(capabilities)
        
        # Detect GPU and CUDA
        self._detect_gpu_info(capabilities)
        
        # Check PyTorch availability
        self._detect_torch_info(capabilities)
        
        # Generate recommendations
        self._generate_recommendations(capabilities)
        
        # Cache results
        self._capabilities = capabilities
        
        # Log summary
        self._log_system_summary(capabilities)
        
        return capabilities
    
    def _detect_cpu_info(self, capabilities: SystemCapabilities):
        """Detect CPU specifications."""
        try:
            if platform.system() == "Linux":
                # Read from /proc/cpuinfo
                with open("/proc/cpuinfo", "r") as f:
                    cpuinfo = f.read()
                
                # Count physical cores and logical processors
                cores = cpuinfo.count("processor")
                capabilities.cpu_threads = cores
                
                # Try to get physical core count
                try:
                    result = subprocess.run(
                        ["nproc", "--all"], 
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        capabilities.cpu_threads = int(result.stdout.strip())
                except:
                    pass
                
                # Try to get physical core count
                try:
                    result = subprocess.run(
                        ["lscpu"], 
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        for line in result.stdout.split('\n'):
                            if 'Core(s) per socket:' in line:
                                cores_per_socket = int(line.split(':')[1].strip())
                            if 'Socket(s):' in line:
                                sockets = int(line.split(':')[1].strip())
                                capabilities.cpu_cores = cores_per_socket * sockets
                            if 'Model name:' in line:
                                capabilities.cpu_name = line.split(':')[1].strip()
                except:
                    pass
                
                # Fallback
                if capabilities.cpu_cores == 0:
                    capabilities.cpu_cores = capabilities.cpu_threads // 2  # Assume hyperthreading
                    
            else:
                # Windows/macOS fallback
                capabilities.cpu_threads = os.cpu_count() or 1
                capabilities.cpu_cores = capabilities.cpu_threads // 2
                
        except Exception as e:
            self.logger.warning(f"Could not detect CPU info: {e}")
            capabilities.cpu_threads = os.cpu_count() or 1
            capabilities.cpu_cores = capabilities.cpu_threads // 2
    
    def _detect_memory_info(self, capabilities: SystemCapabilities):
        """Detect system memory information."""
        try:
            if platform.system() == "Linux":
                with open("/proc/meminfo", "r") as f:
                    meminfo = f.read()
                
                for line in meminfo.split('\n'):
                    if line.startswith('MemTotal:'):
                        total_kb = int(line.split()[1])
                        capabilities.total_ram_gb = total_kb / (1024 * 1024)
                    elif line.startswith('MemAvailable:'):
                        available_kb = int(line.split()[1])
                        capabilities.available_ram_gb = available_kb / (1024 * 1024)
                        
            else:
                # Basic fallback for other systems
                import psutil
                memory = psutil.virtual_memory()
                capabilities.total_ram_gb = memory.total / (1024**3)
                capabilities.available_ram_gb = memory.available / (1024**3)
                
        except Exception as e:
            self.logger.warning(f"Could not detect memory info: {e}")
            capabilities.total_ram_gb = 8.0  # Conservative fallback
            capabilities.available_ram_gb = 4.0
    
    def _detect_gpu_info(self, capabilities: SystemCapabilities):
        """Detect NVIDIA GPU and CUDA information."""
        capabilities.gpus = []
        
        # Check for nvidia-smi
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", 
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0 and result.stdout.strip():
                capabilities.has_nvidia_gpu = True
                
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        parts = [p.strip() for p in line.split(',')]
                        if len(parts) >= 3:
                            gpu_info = GPUInfo(
                                name=parts[0],
                                memory_mb=int(parts[1]),
                                driver_version=parts[2]
                            )
                            capabilities.gpus.append(gpu_info)
                            
        except Exception as e:
            self.logger.debug(f"nvidia-smi not available: {e}")
        
        # Check for CUDA toolkit
        try:
            result = subprocess.run(
                ["nvcc", "--version"],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode == 0:
                capabilities.has_cuda = True
                # Extract CUDA version
                for line in result.stdout.split('\n'):
                    if 'release' in line.lower():
                        # Update GPU info with CUDA version
                        cuda_version = line.split('release')[1].split(',')[0].strip()
                        for gpu in capabilities.gpus:
                            gpu.cuda_version = cuda_version
                        break
                        
        except Exception as e:
            self.logger.debug(f"CUDA toolkit not available: {e}")
    
    def _detect_torch_info(self, capabilities: SystemCapabilities):
        """Detect PyTorch availability and CUDA support."""
        try:
            import torch
            capabilities.torch_available = True
            
            if torch.cuda.is_available():
                capabilities.torch_cuda_available = True
                capabilities.recommended_device = "cuda"
                
                # Get detailed CUDA info
                for i in range(torch.cuda.device_count()):
                    device_props = torch.cuda.get_device_properties(i)
                    if i < len(capabilities.gpus):
                        capabilities.gpus[i].compute_capability = f"{device_props.major}.{device_props.minor}"
            else:
                capabilities.recommended_device = "cpu"
                
        except ImportError:
            self.logger.debug("PyTorch not available")
            capabilities.torch_available = False
    
    def _generate_recommendations(self, capabilities: SystemCapabilities):
        """Generate Whisper model recommendations based on hardware."""
        recommendations = []
        
        if capabilities.torch_cuda_available and capabilities.gpus:
            # GPU-based recommendations
            max_vram_gb = max(gpu.memory_mb for gpu in capabilities.gpus) / 1024
            
            if max_vram_gb >= 10:
                recommendations = ["tiny", "base", "small", "medium", "large"]
                capabilities.max_recommended_model = "large"
            elif max_vram_gb >= 5:
                recommendations = ["tiny", "base", "small", "medium"]
                capabilities.max_recommended_model = "medium"
            elif max_vram_gb >= 2:
                recommendations = ["tiny", "base", "small"]
                capabilities.max_recommended_model = "small"
            else:
                recommendations = ["tiny", "base"]
                capabilities.max_recommended_model = "base"
                
        else:
            # CPU-based recommendations
            if capabilities.available_ram_gb >= 16 and capabilities.cpu_cores >= 8:
                recommendations = ["tiny", "base", "small"]
                capabilities.max_recommended_model = "small"
            elif capabilities.available_ram_gb >= 8 and capabilities.cpu_cores >= 4:
                recommendations = ["tiny", "base"]
                capabilities.max_recommended_model = "base"
            else:
                recommendations = ["tiny"]
                capabilities.max_recommended_model = "tiny"
        
        capabilities.recommended_models = recommendations
    
    def _log_system_summary(self, capabilities: SystemCapabilities):
        """Log a summary of detected system capabilities."""
        self.logger.info("🖥️  System Hardware Summary:")
        self.logger.info(f"   CPU: {capabilities.cpu_name}")
        self.logger.info(f"   Cores: {capabilities.cpu_cores} physical, {capabilities.cpu_threads} logical")
        self.logger.info(f"   RAM: {capabilities.total_ram_gb:.1f}GB total, {capabilities.available_ram_gb:.1f}GB available")
        
        if capabilities.has_nvidia_gpu:
            self.logger.info(f"   GPU: {len(capabilities.gpus)} NVIDIA GPU(s) detected")
            for i, gpu in enumerate(capabilities.gpus):
                self.logger.info(f"     GPU {i+1}: {gpu.name} ({gpu.memory_mb/1024:.1f}GB)")
                if gpu.cuda_version:
                    self.logger.info(f"             CUDA {gpu.cuda_version}, Compute {gpu.compute_capability or 'Unknown'}")
        else:
            self.logger.info("   GPU: No NVIDIA GPU detected")
        
        self.logger.info(f"   PyTorch: {'✅' if capabilities.torch_available else '❌'}")
        self.logger.info(f"   CUDA Support: {'✅' if capabilities.torch_cuda_available else '❌'}")
        self.logger.info(f"   Recommended Device: {capabilities.recommended_device}")
        self.logger.info(f"   Recommended Models: {', '.join(capabilities.recommended_models)}")
        self.logger.info(f"   Max Recommended: {capabilities.max_recommended_model}")


class WhisperConfig:
    """Configuration manager for Whisper processing options."""
    
    # Model sizes and requirements
    MODEL_INFO = {
        "tiny": {
            "size_mb": 39,
            "vram_mb": 1024,
            "ram_mb": 1024,
            "relative_speed": 32,
            "languages": "English only",
            "description": "Fastest, least accurate"
        },
        "base": {
            "size_mb": 74,
            "vram_mb": 1024,
            "ram_mb": 2048,
            "relative_speed": 16,
            "languages": "Multilingual",
            "description": "Fast, good accuracy"
        },
        "small": {
            "size_mb": 244,
            "vram_mb": 2048,
            "ram_mb": 4096,
            "relative_speed": 6,
            "languages": "Multilingual", 
            "description": "Balanced speed/accuracy"
        },
        "medium": {
            "size_mb": 769,
            "vram_mb": 5120,
            "ram_mb": 8192,
            "relative_speed": 2,
            "languages": "Multilingual",
            "description": "Slower, high accuracy"
        },
        "large": {
            "size_mb": 1550,
            "vram_mb": 10240,
            "ram_mb": 16384,
            "relative_speed": 1,
            "languages": "Multilingual",
            "description": "Slowest, highest accuracy"
        }
    }
    
    @classmethod
    def get_model_info(cls, model_name: str) -> Dict:
        """Get information about a specific Whisper model."""
        return cls.MODEL_INFO.get(model_name, {})
    
    @classmethod
    def validate_model_for_system(cls, model_name: str, capabilities: SystemCapabilities) -> Tuple[bool, str]:
        """
        Validate if a model can run on the current system.
        
        Returns:
            Tuple of (can_run, reason)
        """
        model_info = cls.get_model_info(model_name)
        if not model_info:
            return False, f"Unknown model: {model_name}"
        
        if capabilities.torch_cuda_available and capabilities.gpus:
            # GPU validation
            max_vram_mb = max(gpu.memory_mb for gpu in capabilities.gpus)
            required_vram_mb = model_info["vram_mb"]
            
            if max_vram_mb < required_vram_mb:
                return False, f"Insufficient VRAM: need {required_vram_mb}MB, have {max_vram_mb}MB"
                
        else:
            # CPU validation
            required_ram_mb = model_info["ram_mb"]
            available_ram_mb = capabilities.available_ram_gb * 1024
            
            if available_ram_mb < required_ram_mb:
                return False, f"Insufficient RAM: need {required_ram_mb}MB, have {available_ram_mb:.0f}MB"
        
        return True, "Compatible"
    
    @classmethod
    def get_optimal_model(cls, capabilities: SystemCapabilities, prefer_speed: bool = True) -> str:
        """
        Get the optimal model for the current system.
        
        Args:
            capabilities: System capabilities
            prefer_speed: If True, prefer faster models; if False, prefer accuracy
            
        Returns:
            Recommended model name
        """
        if prefer_speed:
            # Return fastest compatible model
            for model in ["tiny", "base", "small", "medium", "large"]:
                can_run, _ = cls.validate_model_for_system(model, capabilities)
                if can_run:
                    return model
        else:
            # Return most accurate compatible model
            for model in ["large", "medium", "small", "base", "tiny"]:
                can_run, _ = cls.validate_model_for_system(model, capabilities)
                if can_run:
                    return model
        
        return "tiny"  # Ultra-conservative fallback


def get_system_capabilities() -> SystemCapabilities:
    """
    Get cached system capabilities, detecting them if necessary.
    
    Returns:
        SystemCapabilities object with all hardware information
    """
    detector = HardwareDetector()
    return detector.detect_system_capabilities()


def get_whisper_config_summary() -> str:
    """
    Get a formatted summary of Whisper configuration options.
    
    Returns:
        Multi-line string with configuration information
    """
    capabilities = get_system_capabilities()
    config = WhisperConfig()
    
    summary = ["🎯 Local Whisper Configuration Summary", "=" * 50]
    
    # System info
    summary.append(f"System: {capabilities.cpu_name}")
    summary.append(f"RAM: {capabilities.available_ram_gb:.1f}GB available")
    
    if capabilities.torch_cuda_available:
        for gpu in capabilities.gpus:
            summary.append(f"GPU: {gpu.name} ({gpu.memory_mb/1024:.1f}GB)")
        summary.append(f"Recommended Device: CUDA")
    else:
        summary.append(f"Recommended Device: CPU")
    
    summary.append("")
    summary.append("Available Models:")
    
    for model_name in ["tiny", "base", "small", "medium", "large"]:
        model_info = config.get_model_info(model_name)
        can_run, reason = config.validate_model_for_system(model_name, capabilities)
        
        status = "✅" if can_run else "❌"
        summary.append(f"  {status} {model_name:6} - {model_info['description']} ({model_info['size_mb']}MB)")
        
        if not can_run:
            summary.append(f"      Reason: {reason}")
    
    summary.append("")
    summary.append(f"Optimal Model (Speed): {config.get_optimal_model(capabilities, prefer_speed=True)}")
    summary.append(f"Optimal Model (Quality): {config.get_optimal_model(capabilities, prefer_speed=False)}")
    
    return "\n".join(summary)


if __name__ == "__main__":
    # Test hardware detection
    print(get_whisper_config_summary())