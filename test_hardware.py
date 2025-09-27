#!/usr/bin/env python3
"""
Hardware detection and local Whisper validation script.

This script tests the hardware detection system and validates local Whisper
setup without actually processing audio files.
"""

import os
import sys
from pathlib import Path

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_hardware_detection():
    """Test hardware detection capabilities."""
    print("🔍 Testing Hardware Detection System")
    print("=" * 50)
    
    try:
        from subshift.hardware import get_system_capabilities, get_whisper_config_summary
        
        # Get system capabilities
        capabilities = get_system_capabilities()
        
        print("\n📊 System Summary:")
        print(f"   CPU: {capabilities.cpu_name}")
        print(f"   Cores: {capabilities.cpu_cores} physical, {capabilities.cpu_threads} logical")
        print(f"   RAM: {capabilities.total_ram_gb:.1f}GB total, {capabilities.available_ram_gb:.1f}GB available")
        
        if capabilities.has_nvidia_gpu:
            print(f"   GPU: {len(capabilities.gpus)} NVIDIA GPU(s)")
            for gpu in capabilities.gpus:
                print(f"      {gpu.name} ({gpu.memory_mb/1024:.1f}GB)")
        else:
            print("   GPU: No NVIDIA GPU detected")
            
        print(f"   PyTorch: {'✅' if capabilities.torch_available else '❌'}")
        print(f"   CUDA: {'✅' if capabilities.torch_cuda_available else '❌'}")
        print(f"   Recommended Device: {capabilities.recommended_device}")
        
        print("\n🎯 Whisper Configuration Summary:")
        print(get_whisper_config_summary())
        
        return True
        
    except Exception as e:
        print(f"❌ Hardware detection failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_transcription_engines():
    """Test transcription engine creation."""
    print("\n🔧 Testing Transcription Engine Creation")
    print("=" * 50)
    
    try:
        from subshift.transcribe import create_transcription_engine, LocalWhisperEngine
        
        # Test engine availability checks
        print("\n📋 Checking Engine Requirements:")
        
        # Check Whisper availability
        whisper_ok, whisper_msg = LocalWhisperEngine._check_whisper_availability()
        print(f"   Whisper: {'✅' if whisper_ok else '❌'} {whisper_msg}")
        
        # Check PyTorch availability  
        torch_ok, torch_msg = LocalWhisperEngine._check_torch_availability()
        print(f"   PyTorch: {'✅' if torch_ok else '❌'} {torch_msg}")
        
        # Test engine creation (without actually initializing models)
        print("\n🏗️  Testing Engine Creation:")
        
        # Set disable flag to prevent actual model loading
        os.environ['SUBSHIFT_DISABLE_LOCAL_WHISPER'] = '1'
        
        try:
            # This should fail gracefully due to disable flag
            engine = create_transcription_engine("local-base")
            print("   ❌ Engine creation should have failed (disabled)")
        except RuntimeError as e:
            if "disabled" in str(e).lower():
                print("   ✅ Local Whisper correctly disabled")
            else:
                print(f"   ❌ Unexpected error: {e}")
        
        # Remove disable flag
        del os.environ['SUBSHIFT_DISABLE_LOCAL_WHISPER']
        
        # Test validation without model loading
        print("\n🔍 Testing Model Validation:")
        for model in ["tiny", "base", "small", "medium", "large"]:
            try:
                from subshift.hardware import get_system_capabilities, WhisperConfig
                capabilities = get_system_capabilities()
                config = WhisperConfig()
                
                can_run, reason = config.validate_model_for_system(model, capabilities)
                status = "✅" if can_run else "❌"
                print(f"   {status} {model:6} - {reason}")
                
            except Exception as e:
                print(f"   ❌ {model:6} - Validation error: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Engine testing failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_environment_checks():
    """Test environment and dependency checks."""
    print("\n🌍 Testing Environment")
    print("=" * 50)
    
    # Check Python version
    print(f"Python: {sys.version}")
    
    # Check key dependencies
    dependencies = {
        "openai": "OpenAI API client",
        "torch": "PyTorch deep learning framework", 
        "whisper": "OpenAI Whisper (local)",
        "ffmpeg": "FFmpeg audio processing (not Python package)",
        "numpy": "Numerical computing",
        "tqdm": "Progress bars"
    }
    
    print("\n📦 Dependencies:")
    for dep, desc in dependencies.items():
        try:
            if dep == "ffmpeg":
                # Special case - check system command
                import subprocess
                result = subprocess.run(["ffmpeg", "-version"], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    version = result.stdout.split('\n')[0]
                    print(f"   ✅ {dep:12} - {version}")
                else:
                    print(f"   ❌ {dep:12} - Not found or error")
            else:
                # Python package
                module = __import__(dep)
                version = getattr(module, '__version__', 'Unknown version')
                print(f"   ✅ {dep:12} - v{version}")
        except ImportError:
            print(f"   ❌ {dep:12} - Not installed")
        except Exception as e:
            print(f"   ⚠️  {dep:12} - Error: {e}")
    
    # Check CUDA environment
    print("\n🚀 CUDA Environment:")
    cuda_vars = [
        "CUDA_VISIBLE_DEVICES",
        "CUDA_DEVICE_ORDER", 
        "TORCH_HOME",
        "SUBSHIFT_DISABLE_LOCAL_WHISPER"
    ]
    
    for var in cuda_vars:
        value = os.getenv(var)
        if value:
            print(f"   {var}: {value}")
        else:
            print(f"   {var}: Not set")
    
    return True


def main():
    """Run all hardware tests."""
    print("🧪 SubShift Hardware Detection & Local Whisper Test")
    print("=" * 60)
    
    tests = [
        ("Hardware Detection", test_hardware_detection),
        ("Environment Checks", test_environment_checks),
        ("Transcription Engines", test_transcription_engines),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🔬 Running: {test_name}")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ Test {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if success:
            passed += 1
    
    print(f"\nResults: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! Local Whisper setup is ready.")
        print("\n💡 Next steps:")
        print("   1. To test with GPU, install CUDA and run again")
        print("   2. To enable local Whisper, remove SUBSHIFT_DISABLE_LOCAL_WHISPER")
        print("   3. Use --api local-base in subshift commands")
    else:
        print("⚠️  Some tests failed. Check the output above for issues.")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())