import subprocess
import os
import threading
import queue
import time
import re

# Git Bash 固定路径
GIT_BASH_PATH = r'C:\Program Files\Git\bin\bash.exe'

class BashSession:
    """持久化的Git Bash交互式会话,支持 with 语句"""
    
    def __init__(self, cwd=None, timeout=30):
        self.cwd = cwd or os.getcwd()
        self.git_bash = GIT_BASH_PATH
        self.timeout = timeout
        self.process = None
        self.stderr_queue = queue.Queue()
        self.stderr_thread = None
        self._marker_pattern = None  # 用于过滤标记
        self._check_git_bash()
        self._start_session()
    
    def _check_git_bash(self):
        if not os.path.exists(self.git_bash):
            raise FileNotFoundError(f"❌ 找不到 {self.git_bash}")
    
    def _stderr_reader(self):
        """后台线程持续读取stderr,避免管道阻塞"""
        try:
            for line in iter(self.process.stderr.readline, ''):
                if line:
                    self.stderr_queue.put(line)
        except (ValueError, OSError):
            pass
    
    def _start_session(self):
        """启动持久化bash进程"""
        self.process = subprocess.Popen(
            [self.git_bash, '--login'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=self.cwd,
            bufsize=1,
            universal_newlines=True,
            encoding='utf-8'  # 明确指定UTF-8编码
        )
        
        # 启动stderr读取线程
        self.stderr_thread = threading.Thread(
            target=self._stderr_reader, 
            daemon=True
        )
        self.stderr_thread.start()
        
        # 初始化:关闭回显和提示符
        init_commands = [
            'set +v',  # 关闭详细模式
            'set +x',  # 关闭命令回显
            'export PS1=""',
            'export PS2=""',
            'export PS4=""',
            'export LANG=zh_CN.UTF-8',  # 设置中文环境
            'export LC_ALL=zh_CN.UTF-8',  # 设置所有locale为中文UTF-8
            f'cd "{self.cwd}"'
        ]
        for cmd in init_commands:
            self.process.stdin.write(cmd + '\n')
        self.process.stdin.flush()
        time.sleep(0.15)
        
        # 清空初始化产生的输出
        self._drain_output()

    
    def _drain_output(self):
        """清空当前缓冲区中的所有输出"""
        while not self.stderr_queue.empty():
            try:
                self.stderr_queue.get_nowait()
            except queue.Empty:
                break
    
    def run_command(self, command, timeout=None):
        """在同一会话中执行命令"""
        if self.process.poll() is not None:
            raise RuntimeError("Bash进程已终止")
        
        timeout = timeout or self.timeout
        marker_start = f"___START_{int(time.time()*1000000)}___"
        marker_end = f"___END_{int(time.time()*1000000)}___"
        
        # 存储当前标记,用于过滤stderr
        self._marker_pattern = re.compile(
            f'({re.escape(marker_start)}|{re.escape(marker_end)}|echo.*___(?:START|END)_)'
        )
        
        # 构造命令
        full_cmd = f'echo "{marker_start}"\n{command}\necho "{marker_end}:$?"\n'
        # print(f"🚀 执行命令: {command}")
        # print(f"📝 完整命令:\n{full_cmd}")
        try:
            self.process.stdin.write(full_cmd)
            self.process.stdin.flush()
        except (OSError, ValueError) as e:
            raise RuntimeError("无法向bash进程写入命令,可能已终止") from e
        
        # 读取输出
        output_lines = []
        stderr_lines = []
        start_time = time.time()
        found_start = False
        returncode = None
        
        while True:
            if time.time() - start_time > timeout:
                raise TimeoutError(f"命令执行超时({timeout}秒): {command}")
            
            try:
                line = self.process.stdout.readline()
                if not line:
                    break
                
                if marker_start in line:
                    found_start = True
                    continue
                
                if marker_end in line and found_start:
                    try:
                        returncode = int(line.split(':')[-1].strip())
                    except ValueError:
                        returncode = -1
                    break
                
                if found_start:
                    output_lines.append(line)
                    
            except (OSError, ValueError):
                break
        
        # 收集stderr并过滤标记
        while not self.stderr_queue.empty():
            try:
                line = self.stderr_queue.get_nowait()
                # 过滤掉标记相关的行
                if not self._marker_pattern.search(line):
                    stderr_lines.append(line)
            except queue.Empty:
                break
        
        return {
            'stdout': ''.join(output_lines).rstrip('\n'),
            'stderr': ''.join(stderr_lines).rstrip('\n'),
            'returncode': returncode if returncode is not None else -1,
            'success': returncode == 0 if returncode is not None else False
        }
    
    def is_alive(self):
        """检查会话是否存活"""
        return self.process and self.process.poll() is None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.process:
            if self.process.poll() is None:
                try:
                    self.process.stdin.write('exit\n')
                    self.process.stdin.flush()
                    self.process.wait(timeout=2)
                except (OSError, ValueError, subprocess.TimeoutExpired):
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
            
            for pipe in [self.process.stdin, self.process.stdout, self.process.stderr]:
                if pipe:
                    try:
                        pipe.close()
                    except:
                        pass


# ============ 使用示例 ============
if __name__ == '__main__':
    try:
        with BashSession() as bash:
            # 测试1: 普通命令
            # result = bash.run_command("""python.exe -c 'print("❤爱你中国")'""") # python.exe这种需要处理
            # print(f"✅ stdout: {result['stdout']}") 
            # print(f"📊 returncode: {result['returncode']}\n")
            
            # 测试2: 错误命令(产生真正的stderr)
            result = bash.run_command('mv "/c/Users/Administrator/Desktop/新建文件夹/test.txt" "/c/Users/Administrator/Desktop/新建文件夹/test2.txt"')
            print(f"❌ stderr: {result['stderr']}")
            print(f"📊 returncode: {result['returncode']}\n")
            
            # 测试3: 同时有stdout和stderr
            # result = bash.run_command('echo "正常输出" && ls /notexist 2>&1')
            # print(f"📤 stdout: {result['stdout']}")
            # print(f"📥 stderr: {result['stderr']}")
            # print(f"📊 returncode: {result['returncode']}\n")
            
    except Exception as e:
        print(f"💥 错误: {e}")
