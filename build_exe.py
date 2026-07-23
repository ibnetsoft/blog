import os
import subprocess
import sys
import shutil

def build():
    print("=" * 60)
    print("  SNS Studio EXE Build Process Starting")
    print("=" * 60)

    # 1. 빌드 관련 폴더 정리
    for folder in ['build', 'dist']:
        if os.path.exists(folder):
            print(f"  - Deleting existing {folder} folder...")
            shutil.rmtree(folder, ignore_errors=True)

    # 2. PyInstaller 커맨드 구성
    # --onefile: 단일 파일 생성
    # --noconfirm: 질문 없이 진행
    # --clean: 캐시 정리
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "SNS_Studio_Blog",
        "--noconfirm",
        "--clean",
        "--add-data", "templates;templates",
        "--add-data", "static;static",
        # FastAPI / Uvicorn 필수 히든 임포트
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols",
        "--hidden-import", "uvicorn.protocols.http",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.http.h11_impl",
        "--hidden-import", "uvicorn.protocols.websockets",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "uvicorn.lifespan",
        "--hidden-import", "uvicorn.lifespan.on",
        "--hidden-import", "anyio._backends._asyncio",
        "--hidden-import", "jinja2.ext",
        "main.py"
    ]

    print(f"\n  - Running build command...")
    
    try:
        subprocess.check_call(cmd)
        print("\n" + "=" * 60)
        print("  Build Successful!")
        print("  Location: 'dist/SNS_Studio_Blog.exe'")
        print("=" * 60)
    except subprocess.CalledProcessError as e:
        print(f"\n  ❌ Build Failed: {e}")
    except Exception as e:
        print(f"\n  ❌ Error: {e}")

if __name__ == "__main__":
    build()
