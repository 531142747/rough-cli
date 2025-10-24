# rough-cli

一个基于 Claude AI 的轻量级 CLI 工具，通过 Git Bash 执行 Linux 命令来完成各种任务。

## 设计理念

本项目采用简洁的设计思路：
- 使用标准 Linux 命令而非自定义工具
- 避免上下文膨胀，充分利用大模型对 Linux 命令的理解
- 基于 Git Bash 环境，保证命令兼容性

## 前置条件

1. **安装依赖**
```bash
pip install openai
```

2. **环境要求**
- Git Bash (Windows 用户)
- 或任意 Linux/MacOS 终端环境

## 安装使用

```bash
# 克隆项目
git clone <repository-url>
cd rough-cli

# 运行
python main.py
```

## 特性

- ✅ 轻量级设计，最小化上下文占用
- ✅ 基于标准 Linux 命令
- ✅ 支持 Claude AI 智能交互
- ✅ Git Bash 环境友好

## 配置

需要配置 OpenAI API 相关环境变量或配置文件。
