"""
Quick start script for the Advanced RAG Question Generator.
Runs both backend and frontend.
"""
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

def main():
    print("=" * 60)
    print("🚀 Starting Advanced RAG Question Generator (v2.0)")
    print("=" * 60)
    
    # Check if we're in the right directory
    project_root = Path(__file__).parent
    backend_dir = project_root / "backend"
    frontend_dir = project_root / "frontend"
    
    if not backend_dir.exists() or not frontend_dir.exists():
        print("❌ Error: backend or frontend directory not found!")
        print(f"Current directory: {project_root}")
        return
    
    print("\n📦 Starting Backend API...")
    print("   URL: http://localhost:8601")
    print("   Backend will run in background...")
    
    # Start backend
    backend_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8601"],
        cwd=backend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    
    # Wait for backend to start
    print("\n⏳ Waiting for backend to initialize (10 seconds)...")
    time.sleep(10)
    
    print("\n🎨 Starting Frontend UI...")
    print("   URL: http://localhost:8602")
    print("   Opening browser...")
    
    # Start frontend
    frontend_process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "streamlit_app.py", "--server.port", "8602"],
        cwd=frontend_dir,
    )
    
    # Open browser
    time.sleep(3)
    webbrowser.open("http://localhost:8602")
    
    print("\n" + "=" * 60)
    print("✅ System is running!")
    print("=" * 60)
    print("\n📝 Usage:")
    print("   1. Go to 'Knowledge Addition' tab")
    print("   2. Enter folder path with your PDFs/documents")
    print("   3. Click 'Start Ingestion' to load documents")
    print("   4. Go to 'Query & Questions' tab to search and generate questions")
    print("\n💡 Features:")
    print("   - Smart Chunking (keeps formulas/examples intact)")
    print("   - Hybrid Search (semantic + keyword)")
    print("   - Content Classification (theory/formula/exercise)")
    print("   - Auto-Resumable (restarts from where it left off)")
    print("\n⌨️  Press Ctrl+C to stop both backend and frontend")
    print("=" * 60)
    
    try:
        # Keep running
        backend_process.wait()
        frontend_process.wait()
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")
        backend_process.terminate()
        frontend_process.terminate()
        print("✅ Shutdown complete")

if __name__ == "__main__":
    main()
