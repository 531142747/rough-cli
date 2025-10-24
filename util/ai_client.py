from openai import OpenAI
from .tool import read_prompt

# 系统提示词
CLI_PROMPT: str = read_prompt('cli.md')
MODEL: str = "qwen3-max"
# CLI_PROMPT: str = '你是一个智能助手，请根据用户输入回答问题。'


class ChatClient:
    
    def __init__(self, api_key: str = "sk-8DWwOFPCb4gXHMxxx", base_url: str = "http://10.2.3.21:3008/v1", model: str = MODEL, system_prompt: str = None):
        self.api_key = api_key
        self.base_url = base_url
        if not system_prompt:
            system_prompt = CLI_PROMPT
        self.system_prompt = system_prompt
        self.model = model
        self.messages = [
            {"role": "system", "content": system_prompt}
        ]
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.last_usage = None

    def send_msg_steam(self, user_message: str):
        """
        生成器模式:逐块yield响应内容，检测finish_reason提前退出
        """
        # 添加用户消息
        self.messages.append({"role": "user", "content": user_message})
        
        # 调用流式接口
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            stream=True
        )
        
        full_response = ""
        self.last_usage = None
        for chunk in stream:
            # 检查是否有 finish_reason，如果有说明流已结束
            if not chunk.choices:
                continue
            # 检查是否有 usage 信息（通常在最后一个 chunk 中）
            if hasattr(chunk, 'usage') and chunk.usage is not None:
                self.last_usage = chunk.usage
            if hasattr(chunk.choices[0], 'finish_reason') and chunk.choices[0].finish_reason is not None:
                break
            content = chunk.choices[0].delta.content
            if content is not None:
                full_response += content
                yield content
        
        # 如果没有在流中获取到 usage，尝试从完整响应中获取
        if self.last_usage is None:
            try:
                # 获取非流式响应以获取 usage 信息
                non_stream_response = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages,
                    stream=False
                )
                self.last_usage = non_stream_response.usage
            except:
                pass
        
        # 添加助手回复到历史
        self.messages.append({"role": "assistant", "content": full_response})

    def clear(self):
        """清空对话历史(保留 system prompt)"""
        self.messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        self.last_usage = None

    def send_msg(self, user_message: str):
        """发送消息并返回完整回复"""
        return ''.join(self.send_msg_steam(user_message))

    def cost(self):
        """
        显示消耗的token信息
        返回字典包含: prompt_tokens, completion_tokens, total_tokens
        如果没有可用的usage信息，返回None
        """
        if self.last_usage is None:
            return None
        
        usage_info = {
            "prompt_tokens": getattr(self.last_usage, 'prompt_tokens', 0),
            "completion_tokens": getattr(self.last_usage, 'completion_tokens', 0),
            "total_tokens": getattr(self.last_usage, 'total_tokens', 0)
        }
        return usage_info


if __name__ == "__main__":
    # 替换为你的实际密钥(但建议在环境变量中管理)
    chat = ChatClient()
    
    # 方式1: 逐块打印(实时流式输出)
    for msg in ['你好','介绍下你自己']:
        print("AI回复:", end="", flush=True)
        for chunk in chat.send_msg_steam(msg):
            print(chunk, end="", flush=True)
        usage = chat.cost()
        if usage:
            print(f"\nToken消耗: {usage}")
        
    # 方式2: 收集完整回复
    # print( chat.send_msg("你好!"))
    # 获取 token 消耗信息
    chat.clear()  # 清空上下文
