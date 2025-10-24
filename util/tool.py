import os
import re

def read_prompt(filename):
    if not os.path.exists(filename):
        filename = os.path.join('config\prompt', filename)
    with open(filename, 'r', encoding='utf-8') as f:
        return f.read()

def convert_windows_path(path_str):
    """
    TURBO: ➕ 新增功能 - 判断并转换Windows路径为Unix风格
    TURBO: 🔧 修复路径匹配问题 - 支持路径嵌入在文本中
    
    规则：
    - C:\\Users\\a -> /c/Users/a
    - C:/Users/a -> /c/Users/a
    支持路径包含在任意文本中
    """
    # 匹配任意位置的Windows路径模式
    def replace_func(match):
        drive_letter = match.group(1).lower()
        remaining_path = match.group(2).replace('\\', '/')
        return f'/{drive_letter}/{remaining_path}'
    
    # 在字符串任意位置查找并替换Windows路径
    pattern = r'([A-Za-z]):[\\/](\S*)'
    result = re.sub(pattern, replace_func, path_str)
    return result

if __name__ == "__main__":
    # 测试代码
    test_paths = [
        r"测试 C:\Users\Administrator\Desktop\新建文件夹 阿松大",
        r"C:/Users/a/Documents/file.txt",
        r"/home/user/file.txt"
    ]
    
    for path in test_paths:
        converted_path = convert_windows_path(path)
        print(f"Original: {path} -> Converted: {converted_path}")