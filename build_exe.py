import os
import subprocess
import sys
import shutil

def build():
    print("=" * 50)
    print("  SNS Studio EXE 빌드 시작")
    print("=" * 50)

    # 1. 빌드 관련 폴더 정리
    for folder in ['build', 'dist']:
        if os.path.exists(folder):
            print(f"기존 {folder} 폴더 삭제 중...")
            shutil.rmtree(folder)

    # 2. PyInstaller 커맨드 구성
    # --onefile: 단일 파일 생성
    # --add-data: 리소스 포함 (윈도우는 ; 구분자 사용)
    # --hidden-import: uvicorn 전용 모듈 강제 포함
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "SNS_Studio",
        "--add-data", "templates;templates",
        "--add-data", "static;static",
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols",
        "--hidden-import", "uvicorn.protocols.http",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.websockets",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "uvicorn.lifespan",
        "--hidden-import", "uvicorn.lifespan.on",
        "main.py"
    ]

    print(f"빌드 커맨드 실행: {' '.join(cmd)}")
    
    try:
        subprocess.check_call(cmd)
        print("\n" + "=" * 50)
        print("빌드 완료! 'dist' 폴더에서 SNS_Studio.exe를 확인하세요.")
        print("=" * 50)
    except subprocess.CalledProcessError as e:
        print(f"\n빌드 실패: {e}")
    except Exception as e:
        print(f"\n오류 발생: {e}")

if __name__ == "__main__":
    build()
