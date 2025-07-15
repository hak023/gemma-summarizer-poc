import subprocess
import sys
import time
import os

def kill_gemma_processes():
    """gemma_summarizer 관련 프로세스 종료"""
    try:
        # tasklist로 Python 프로세스 확인
        result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq python.exe', '/FO', 'CSV'], 
                              capture_output=True, text=True, shell=True)
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')[1:]  # 헤더 제외
            killed_count = 0
            
            for line in lines:
                if line.strip():
                    parts = line.split(',')
                    if len(parts) >= 2:
                        pid = parts[1].strip('"')
                        try:
                            # 프로세스 명령줄 확인
                            cmd_result = subprocess.run(['wmic', 'process', 'where', f'ProcessId={pid}', 'get', 'CommandLine', '/value'], 
                                                      capture_output=True, text=True, shell=True)
                            
                            if cmd_result.returncode == 0 and 'gemma_summarizer' in cmd_result.stdout:
                                print(f"종료 중: PID {pid}")
                                subprocess.run(['taskkill', '/F', '/PID', pid], 
                                             capture_output=True, shell=True)
                                killed_count += 1
                        except:
                            pass
            
            if killed_count > 0:
                print(f"{killed_count}개 gemma_summarizer 프로세스 종료됨")
                time.sleep(2)
            else:
                print("종료할 gemma_summarizer 관련 프로세스가 없습니다.")
        else:
            print("프로세스 목록 확인 실패")
            
    except Exception as e:
        print(f"프로세스 종료 중 오류: {e}")

def force_kill_all_python():
    """모든 Python 프로세스 강제 종료 (주의: 시스템에 영향을 줄 수 있음)"""
    try:
        print("모든 Python 프로세스 강제 종료 중...")
        subprocess.run(['taskkill', '/F', '/IM', 'python.exe'], 
                      capture_output=True, shell=True)
        print("Python 프로세스 강제 종료 완료")
        time.sleep(3)
    except Exception as e:
        print(f"강제 종료 중 오류: {e}")

def cleanup_shared_memory():
    """공유 메모리 정리 (Windows 전용)"""
    try:
        # PowerShell을 사용하여 공유 메모리 정리 시도
        ps_script = """
        try {
            $shm = Get-WmiObject -Class Win32_SharedMemory | Where-Object { $_.Name -like "*gemma_ipc_shm*" }
            if ($shm) {
                Write-Host "공유 메모리 발견: $($shm.Name)"
                $shm | Remove-WmiObject
                Write-Host "공유 메모리 정리 완료"
            } else {
                Write-Host "정리할 공유 메모리가 없습니다"
            }
        } catch {
            Write-Host "공유 메모리 정리 실패: $_"
        }
        """
        
        result = subprocess.run(['powershell', '-Command', ps_script], 
                              capture_output=True, text=True, shell=True)
        
        if result.returncode == 0:
            print("공유 메모리 정리 시도 완료")
        else:
            print("공유 메모리 정리 실패")
            
    except Exception as e:
        print(f"공유 메모리 정리 중 오류: {e}")

def restart_explorer():
    """Windows Explorer 재시작 (공유 메모리 정리를 위해)"""
    try:
        print("Windows Explorer 재시작 중...")
        subprocess.run(['taskkill', '/F', '/IM', 'explorer.exe'], 
                      capture_output=True, shell=True)
        time.sleep(2)
        subprocess.run(['start', 'explorer.exe'], 
                      capture_output=True, shell=True)
        print("Windows Explorer 재시작 완료")
        time.sleep(3)
    except Exception as e:
        print(f"Explorer 재시작 중 오류: {e}")

def main():
    print("=== 이전 프로세스 정리 시작 ===")
    
    # 1. 일반적인 프로세스 종료
    kill_gemma_processes()
    
    # 2. 공유 메모리 정리
    cleanup_shared_memory()
    
    # 3. 강제 종료 (필요시)
    if len(sys.argv) > 1 and sys.argv[1] == "--force":
        force_kill_all_python()
        restart_explorer()
    
    # 4. 다시 한번 일반 종료
    kill_gemma_processes()
    
    print("=== 프로세스 정리 완료 ===")

if __name__ == "__main__":
    main() 