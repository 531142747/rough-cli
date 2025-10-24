import os
import re
from typing import Callable, Dict, List, Optional, Union

# Tkinter imports kept local to support Windows10 environment
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

try:
    # Optional drag-and-drop support via tkinterdnd2 (if available)
    from tkinterdnd2 import DND_FILES, TkinterDnD  # type: ignore
    _DND_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    DND_FILES = None  # type: ignore
    TkinterDnD = None  # type: ignore
    _DND_AVAILABLE = False


class ChatWindow:
    """Tk 窗口，用于接收用户输入（多行文本、支持多文件拖入），并显示消息。

    功能要点：
    - 多行文本输入区
    - 文件列表区（支持拖拽添加/按钮添加、多选删除、清空）
    - 发送按钮：将文件内容与文本拼接为指定格式并显示在消息区域
    - 提供 AI 消息解析方法：解析 <THINK>/<TOOL>/<RESULT>/<NOTE> 结构
      若解析到 <TOOL> 命令，将其传入占位方法 run_tool_command 执行（方法体为 pass）

    对外接口：
    - set_on_send(callback): 设置发送后的回调，参数为拼接后的完整消息字符串
    - compose_user_message(): 生成当前界面文件+文本的指定格式字符串
    - parse_and_handle_ai_message(ai_text): 解析 AI 消息并显示、必要时调用 run_tool_command
    - start(): 启动主循环
    """

    def __init__(self, enable_drag_drop: bool = True) -> None:
        """初始化窗口与控件。

        参数：
        - enable_drag_drop: 是否启用拖拽（若系统未安装 tkinterdnd2，则自动降级）
        """
        self._drag_drop_enabled = enable_drag_drop and _DND_AVAILABLE
        self._on_send_callback: Optional[Callable[[str], None]] = None
        self._file_paths: List[str] = []

        # 根窗口：优先使用支持 DnD 的 Tk 类
        if self._drag_drop_enabled and TkinterDnD is not None:
            print('TkinterDnD is not None')
            self._root = TkinterDnD.Tk()
        else:
            print('TkinterDnD is None')
            self._root = tk.Tk()

        self._root.title("用户输出窗口")
        self._root.minsize(900, 600)

        # 主布局：左右两列，上下消息区
        self._build_widgets()

    def _build_widgets(self) -> None:
        """构建 UI 控件并完成布局。"""
        # 主框架
        main_frame = ttk.Frame(self._root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 水平分割：左侧文件、右侧输入
        columns = ttk.Panedwindow(main_frame, orient=tk.HORIZONTAL)
        columns.pack(fill=tk.BOTH, expand=True)

        # 左侧：文件区
        left_frame = ttk.Frame(columns)
        self._left_frame = left_frame
        columns.add(left_frame, weight=1)

        files_label = ttk.Label(left_frame, text="文件列表（可拖拽）")
        files_label.pack(anchor=tk.W)

        self._files_listbox = tk.Listbox(left_frame, selectmode=tk.EXTENDED, height=12)
        self._files_listbox.pack(fill=tk.BOTH, expand=True)

        # 拖拽绑定
        if self._drag_drop_enabled and DND_FILES is not None:
            try:
                self._files_listbox.drop_target_register(DND_FILES)  # type: ignore[attr-defined]
                self._files_listbox.dnd_bind("<<Drop>>", self._on_drop_files)  # type: ignore[attr-defined]
                dnd_tip = "已启用拖拽：可将文件直接拖入列表"
            except Exception:
                dnd_tip = "拖拽初始化失败，已降级为按钮添加"
                self._drag_drop_enabled = False
        else:
            dnd_tip = "未检测到拖拽支持，请使用‘添加文件’按钮"

        dnd_label = ttk.Label(left_frame, text=dnd_tip, foreground="#666666")
        dnd_label.pack(anchor=tk.W, pady=(4, 6))

        files_btns = ttk.Frame(left_frame)
        files_btns.pack(fill=tk.X, pady=(0, 6))

        add_btn = ttk.Button(files_btns, text="添加文件", command=self._on_add_files)
        add_btn.pack(side=tk.LEFT)

        remove_btn = ttk.Button(files_btns, text="移除所选", command=self._on_remove_selected)
        remove_btn.pack(side=tk.LEFT, padx=(6, 0))

        clear_btn = ttk.Button(files_btns, text="清空文件", command=self._on_clear_files)
        clear_btn.pack(side=tk.LEFT, padx=(6, 0))

        self._files_count_label = ttk.Label(left_frame, text="已选择 0 个文件")
        self._files_count_label.pack(anchor=tk.W)

        # 右侧：文本输入区
        right_frame = ttk.Frame(columns)
        self._right_frame = right_frame
        columns.add(right_frame, weight=2)

        input_label = ttk.Label(right_frame, text="用户输入（多行）")
        input_label.pack(anchor=tk.W)

        self._text_input = tk.Text(right_frame, height=12)
        self._text_input.pack(fill=tk.BOTH, expand=True)

        send_btn = ttk.Button(right_frame, text="发送", command=self._on_send_click)
        send_btn.pack(anchor=tk.E, pady=(6, 0))

        # 底部：消息显示区
        messages_label = ttk.Label(main_frame, text="消息显示")
        messages_label.pack(anchor=tk.W, pady=(8, 0))

        self._messages_view = ScrolledText(main_frame, height=14, state=tk.DISABLED)
        self._messages_view.pack(fill=tk.BOTH, expand=True)

        # 额外的拖拽绑定：整个根窗口、右侧输入区也接受拖拽
        if self._drag_drop_enabled and DND_FILES is not None:
            self._safe_register_drop(self._root)
            self._safe_register_drop(self._right_frame)
            self._safe_register_drop(self._text_input)

    def start(self) -> None:
        """启动 Tk 主循环。"""
        self._root.mainloop()

    def set_on_send(self, callback: Callable[[str], None]) -> None:
        """设置发送后回调。

        参数：
        - callback: 回调函数，入参为拼接后的完整消息字符串
        """
        self._on_send_callback = callback

    def compose_user_message(self) -> str:
        """将当前文件与输入文本拼接为指定格式字符串。

        返回：
        - 格式（文件块已优化为按行编号的 PATH 形式）：
          <FILE PATH="{文件路径}">\n
          1: 行内容\n
          2: 行内容\n
          ...\n
          </FILE>...
          <USERASK>{文本框内容}</USERASK>
        """
        parts: List[str] = []
        for _, file_path in enumerate(self._file_paths, start=1):
            display_path = self._to_unix_drive_path(file_path)
            raw_content = self._read_text_file_safely(file_path)
            lines = raw_content.splitlines()
            numbered = "\n".join(f"{i}: {line}" for i, line in enumerate(lines, start=1))
            parts.append(
                f"<FILE PATH=\"{display_path}\">\n{numbered}\n</FILE>"
            )

        user_text = self._text_input.get("1.0", tk.END).rstrip()
        parts.append(f"<USERASK>{user_text}</USERASK>")
        return "\n".join(parts)

    def parse_and_handle_ai_message(self, ai_text: str) -> Dict[str, Union[str, List[str]]]:
        """解析 AI 消息文本，显示各区块，并在存在多个 <TOOL> 时逐条执行。

        参数：
        - ai_text: 包含 <THINK>/<TOOL>/<RESULT>/<NOTE> 的文本

        返回：
        - 字典，含 keys: think, result, note（字符串）和 tool_cmd（字符串数组）。
        """
        sections = self._extract_ai_sections(ai_text)
        # 展示解析内容（支持多个 TOOL）
        self._display_ai_sections(sections)

        # 依次执行多个工具命令
        tool_cmds = sections.get("tools", [])

        # 对外返回统一字段：tool_cmd 为数组
        return {
            "think": sections.get("think", ""),
            "tool_cmd": tool_cmds,
            "result": sections.get("result", ""),
            "note": sections.get("note", ""),
        }

    # -------------------- 内部事件与工具方法 --------------------

    def _on_add_files(self) -> None:
        """通过文件对话框添加多个文件到列表。"""
        file_paths = filedialog.askopenfilenames(title="选择文件")
        if not file_paths:
            return
        self._add_files(list(file_paths))

    def _on_remove_selected(self) -> None:
        """移除列表中所选文件。"""
        selected_indices = list(self._files_listbox.curselection())
        if not selected_indices:
            return
        # 逆序删除，避免索引移动
        for idx in reversed(selected_indices):
            del self._file_paths[idx]
            self._files_listbox.delete(idx)
        self._refresh_files_count()

    def _on_clear_files(self) -> None:
        """清空所有已添加的文件。"""
        self._file_paths.clear()
        self._files_listbox.delete(0, tk.END)
        self._refresh_files_count()

    def _on_drop_files(self, event: tk.Event) -> None:  # type: ignore[override]
        """拖拽文件进入列表时的处理。

        兼容 tkinterdnd2 的 event.data 路径列表格式。
        """
        try:
            data = event.data  # type: ignore[attr-defined]
            paths = self._split_dnd_paths(data)
            self._add_files(paths)
        except Exception as exc:
            messagebox.showwarning("拖拽失败", f"解析拖拽数据失败：{exc}")

    def _safe_register_drop(self, widget: tk.Misc) -> None:
        """在指定控件上安全注册拖拽目标与回调。"""
        try:
            widget.drop_target_register(DND_FILES)  # type: ignore[attr-defined]
            widget.dnd_bind("<<Drop>>", self._on_drop_files)  # type: ignore[attr-defined]
        except Exception:
            # 忽略注册失败，维持现有功能
            pass

    def _to_unix_drive_path(self, path: str) -> str:
        """将 Windows 盘符路径转换为 /c/... 形式，并统一为正斜杠。

        规则：
        - C:\\Users\\a -> /c/Users/a
        - C:/Users/a -> /c/Users/a
        - 若无盘符（相对路径或 \\server 形式），仅替换分隔符为 '/'
        """
        drive, rest = os.path.splitdrive(path)
        norm_rest = rest.replace("\\", "/")
        if drive:
            letter = drive[0]
            tail = norm_rest.lstrip("/")
            return f"/{letter.lower()}/{tail}" if tail else f"/{letter.lower()}"
        return norm_rest

    def _on_send_click(self) -> None:
        """点击发送：拼接消息并显示，触发可选回调。"""
        message_text = self.compose_user_message()
        self._append_message("USER", message_text)
        if self._on_send_callback is not None:
            try:
                self._on_send_callback(message_text)
            except Exception as exc:
                messagebox.showwarning("回调异常", f"发送回调执行失败：{exc}")

    def _add_files(self, paths: List[str]) -> None:
        """批量添加文件路径至列表，去重并更新 UI。"""
        unique_existing = set(self._file_paths)
        for path in paths:
            norm = os.path.normpath(path)
            if norm in unique_existing:
                continue
            if not os.path.isfile(norm):
                continue
            self._file_paths.append(norm)
            self._files_listbox.insert(tk.END, norm)
        self._refresh_files_count()

    def _refresh_files_count(self) -> None:
        """刷新文件计数显示。"""
        self._files_count_label.config(text=f"已选择 {len(self._file_paths)} 个文件")

    def _append_message(self, sender: str, content: str) -> None:
        """在消息显示区追加一条消息。"""
        self._messages_view.config(state=tk.NORMAL)
        self._messages_view.insert(tk.END, f"[{sender}]\n")
        self._messages_view.insert(tk.END, content + "\n\n")
        self._messages_view.config(state=tk.DISABLED)
        self._messages_view.see(tk.END)

    def _display_ai_sections(self, sections: Dict[str, Union[str, List[str]]]) -> None:
        """将解析出的 AI 区块按结构显示到消息区（支持多个 <TOOL>）。"""
        think = str(sections.get("think", "")).strip()
        tools = sections.get("tools", [])
        result = str(sections.get("result", "")).strip()
        note = str(sections.get("note", "")).strip()

        combined_parts: List[str] = []
        if think:
            combined_parts.append(f"<THINK>\n{think}\n</THINK>")
        # 多个 TOOL 分块展示
        if isinstance(tools, list):
            for tool_cmd in tools:
                tool_cmd_str = str(tool_cmd).strip()
                if tool_cmd_str:
                    combined_parts.append(f"<TOOL>\n{tool_cmd_str}\n</TOOL>")
        else:
            tool_single = str(tools).strip()
            if tool_single:
                combined_parts.append(f"<TOOL>\n{tool_single}\n</TOOL>")
        if result:
            combined_parts.append(f"<RESULT>\n{result}\n</RESULT>")
        if note:
            combined_parts.append(f"<NOTE>\n{note}\n</NOTE>")

        content = "\n".join(combined_parts) if combined_parts else "(AI 消息为空)"
        self._append_message("AI", content)

    def _read_text_file_safely(self, path: str) -> str:
        """以多编码回退策略读取文本文件内容。

        尝试顺序：utf-8 -> gbk -> latin-1。若全部失败，返回空串。
        """
        for enc in ("utf-8", "gbk", "latin-1"):
            try:
                with open(path, "r", encoding=enc, errors="replace") as f:
                    return f.read()
            except Exception:
                continue
        return ""

    def _split_dnd_paths(self, data: str) -> List[str]:
        """解析 tkinterdnd2 的拖拽数据为路径列表。

        兼容带空格路径（用大括号包裹的情况）。
        """
        # 优先使用 tk 的 splitlist（更稳健）
        try:
            return list(self._root.tk.splitlist(data))  # type: ignore[attr-defined]
        except Exception:
            pass

        # 退化解析：使用正则匹配 {path with space} 或普通分隔
        pattern = re.compile(r"\{([^}]+)\}|([^\s]+)")
        paths: List[str] = []
        for match in pattern.finditer(data):
            group = match.group(1) or match.group(2)
            if group:
                paths.append(group)
        return paths

    def _extract_ai_sections(self, text: str) -> Dict[str, Union[str, List[str]]]:
        """从 AI 文本中提取区块：THINK、多个 TOOL、RESULT、NOTE。

        规则：
        - 使用非贪婪匹配，忽略标签内外的前后空白；
        - THINK/RESULT/NOTE 取首个匹配；
        - TOOL 返回所有匹配，按出现顺序组成列表。
        """
        def pick_first(tag: str) -> str:
            pattern = re.compile(rf"\<{tag}\>\s*([\s\S]*?)\s*\</{tag}\>", re.IGNORECASE)
            m = pattern.search(text)
            return m.group(1) if m else ""

        def pick_all(tag: str) -> List[str]:
            pattern = re.compile(rf"\<{tag}\>\s*([\s\S]*?)\s*\</{tag}\>", re.IGNORECASE)
            return [m.group(1) for m in pattern.finditer(text)]

        return {
            "think": pick_first("THINK"),
            "tools": pick_all("TOOL"),
            "result": pick_first("RESULT"),
            "note": pick_first("NOTE"),
        }


def create_user_output_window(enable_drag_drop: bool = True) -> ChatWindow:
    """工厂方法：创建用户输出窗口实例。

    参数：
    - enable_drag_drop: 是否尝试启用拖拽（需系统具备 tkinterdnd2）

    返回：
    - ChatWindow 实例
    """
    return ChatWindow(enable_drag_drop=enable_drag_drop)


def main():
    win = create_user_output_window(enable_drag_drop=True)
    response = win.parse_and_handle_ai_message("""<THINK>
用户希望将文件 1.txt 重命名为 test.py，并写入一段简单的 Python 代码。首先需要执行重命名 操作，然后向新文件中写入代码。
</THINK>
<TOOL>mv "/c/Users/53114/Desktop/新建文件夹(3)/test_table/1.txt" "/c/Users/53114/Desktop/新建文件夹(3)/test_table/test.py"</TOOL>
<TOOL>echo "print('Hello, World!')" > "/c/Users/53114/Desktop/新建文件夹(3)/test_table/test.py"</TOOL>
<NOTE>文件已重命名为 test.py，并写入了简单的 Python 代码。如果需要其他代码内容，请告诉我！</NOTE>""")
    print(response)
if __name__ == "__main__":
    main()