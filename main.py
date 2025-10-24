from util.tk_ui import create_user_output_window
from util.ai_client import ChatClient
from util.bash import BashSession
from util.tool import convert_windows_path

chat = ChatClient()
bash = BashSession()

    
        
if __name__ == "__main__":
    win = create_user_output_window(enable_drag_drop=True)
    def user_send_message(msg):
        """处理用户消息并执行AI返回的命令，直到没有新命令"""
        # 转换路径
        msg = convert_windows_path(msg)
        
        # 循环处理，直到AI不再返回新命令
        while True:
            # 获取AI响应
            ai_response = ''
            print('发送给AI的消息:', msg)
            for chunk in chat.send_msg_steam(msg):
                ai_response += chunk
                print(chunk, end="", flush=True)
            
            # 解析AI响应中的命令
            parsed = win.parse_and_handle_ai_message(ai_response)
            # 如果没有命令需要执行，退出循环
            if not parsed['tool_cmd']:
                break
            
            # 执行所有命令并收集结果
            tool_responses = []
            for i, cmd in enumerate(parsed['tool_cmd'], 1):
                result = bash.run_command(cmd)
                
                # 只有当有输出时才添加到响应列表
                if result['stdout'] or result['stderr']:
                    # 构建工具响应格式
                    error = f"--error_msg--\n{result['stderr']}\n" if result['stderr'] else ""
                    error_info = f"ERROR_CODE={result['returncode']}" if result['returncode'] != 0 else ""
                    tool_res = (
                        f"<TOOL RES {i} {error_info}>"
                        f"{result['stdout']}\n"
                        f"{error}"
                        f"</TOOL RES>"
                    )
                    tool_responses.append(tool_res)
            
            # 如果没有工具输出，退出循环
            if not tool_responses:
                break
            
            # 将工具响应作为新消息发送给AI
            msg = '\n'.join(tool_responses)
        # 打印成本
        print(chat.cost())
            

    # 可选：处理“发送”后的回调
    win.set_on_send(user_send_message)
    # 可选：模拟接收 AI 消息并展示与解析
    # ai_text = "<THINK>...</THINK><TOOL>echo 123</TOOL><RESULT>ok</RESULT><NOTE>提示</NOTE>"
    # win.parse_and_handle_ai_message(ai_text)
    win.start()