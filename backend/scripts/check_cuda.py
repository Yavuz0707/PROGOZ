import platform
import shutil
import sys


def main() -> None:
    selected_device = "cpu"
    print(f"Python: {platform.python_version()}")
    print(f"Executable: {sys.executable}")
    try:
        import torch

        cuda_available = torch.cuda.is_available()
        selected_device = "cuda:0" if cuda_available else "cpu"
        print(f"Torch: {torch.__version__}")
        print(f"CUDA available: {cuda_available}")
        print(f"CUDA version: {torch.version.cuda}")
        print(f"GPU count: {torch.cuda.device_count() if cuda_available else 0}")
        if cuda_available:
            print(f"GPU: {torch.cuda.get_device_name(0)}")
    except Exception as exc:
        print(f"Torch import error: {exc}")

    try:
        import ultralytics

        print(f"Ultralytics: OK ({ultralytics.__version__})")
    except Exception as exc:
        print(f"Ultralytics import error: {exc}")

    try:
        import cv2

        print(f"OpenCV version: {cv2.__version__}")
    except Exception as exc:
        print(f"OpenCV import error: {exc}")

    print(f"FFmpeg: {'OK' if shutil.which('ffmpeg') else 'NOT FOUND'}")

    print(f"Selected device: {selected_device}")


if __name__ == "__main__":
    main()
