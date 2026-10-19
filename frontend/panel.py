import json
import logging
import tkinter as tk
import tkinter.font as tkfont

# ================= 配色 =================
ROW_BLUE = "#E8F2FC"        # 淡蓝（斑马纹 A）
ROW_WHITE = "#FFFFFF"       # 白  （斑马纹 B）
DETAIL_BG = "#F2F7FC"       # 展开详情的底色
DETAIL_BORDER = "#C6D8E8"
HEADER_BG = "#D7E7F6"
TOPBAR_BG = "#FFFFFF"
TEXT_MAIN = "#1F3B52"
TEXT_SUB = "#5A7691"
LINE = "#CBD8E4"
SWITCH_ON = "#5DBE8C"
SWITCH_OFF = "#C9D3DC"
PANEL_BG = "#FFFFFF"

# ================= 自适应 =================
# 基准尺寸：窗口缩到 1000x600 后，再按屏幕分辨率算出的比例系数放大
BASE_WIDTH, BASE_HEIGHT = 1000, 600
# 参照分辨率：该分辨率下比例系数 = 1.0
REF_WIDTH, REF_HEIGHT = 1920, 1080
# 限幅：避免极端屏幕上窗口/字体过大或过小
SCALE_MIN, SCALE_MAX = 0.75, 1.5
# 会随比例缩放的 tk 内置字体
SCALED_FONTS = (
    "TkDefaultFont", "TkTextFont", "TkFixedFont", "TkMenuFont",
    "TkHeadingFont", "TkCaptionFont", "TkSmallCaptionFont",
    "TkIconFont", "TkTooltipFont",
)


def enable_dpi_awareness():
    """
    在创建 Tk() 之前调用：让窗口按真实像素渲染，高 DPI 下不发虚。
    非 Windows 或调用失败时静默跳过。
    """
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def fmt_value(value) -> str:
    """详情面板的值格式化：容器用紧凑 JSON，标量直接 str"""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


class ScrollArea:
    """可滚动的竖向区域（Canvas + 内嵌 Frame），用于左两栏的行列表"""

    def __init__(self, parent, bg=PANEL_BG):
        self.outer = tk.Frame(parent, bg=bg)
        self.canvas = tk.Canvas(self.outer, bg=bg, highlightthickness=0, bd=0)
        self.scrollbar = tk.Scrollbar(self.outer, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)

        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._sync_scrollregion)
        self.canvas.bind("<Configure>", self._sync_width)
        for widget in (self.canvas, self.inner):
            widget.bind("<MouseWheel>", self._on_wheel)

    def _sync_scrollregion(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _sync_width(self, event):
        self.canvas.itemconfigure(self._window, width=event.width)

    def _on_wheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def clear(self):
        for child in self.inner.winfo_children():
            child.destroy()


class FrontendPanel:
    """
    三栏面板：
      session 栏 —— 会话行（斑马纹），点击行在下方展开详情
      mod     栏 —— 选中会话的mod行（斑马纹，展示name + 开关指示），点击行展开详情（展示id等）
      log     栏 —— 选中会话各mod的运行日志
    """

    def __init__(self, data_source, title: str = "火影协议前端", on_close=None, poll_ms: int = 400):
        self.data_source = data_source
        self.on_close = on_close
        self.poll_ms = poll_ms

        self.selected_session_id = None
        self.selected_mod_id = None

        # 渲染签名：与上次一致就跳过重建，避免无谓闪动
        self._session_sig = None
        self._mod_sig = None
        self._log_sig = None

        enable_dpi_awareness()
        self.root = tk.Tk()
        self.root.title(title)

        # 分辨率自适应：算比例系数 → 乘基准尺寸 → 应用到窗口与字体
        self.scale = self._compute_scale()
        self._apply_font_scaling()
        self._apply_geometry()

        self._build_topbar()
        self._build_body()

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._render_all()

    # ================= 自适应 =================
    def _compute_scale(self) -> float:
        """比例系数 = 屏幕分辨率 / 参照分辨率（宽高取较小者），并限幅"""
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        coefficient = min(screen_w / REF_WIDTH, screen_h / REF_HEIGHT)
        return max(SCALE_MIN, min(coefficient, SCALE_MAX))

    def _apply_geometry(self):
        """窗口尺寸 = 基准尺寸 * 比例系数，并居中（略偏上）"""
        width = int(BASE_WIDTH * self.scale)
        height = int(BASE_HEIGHT * self.scale)
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 3)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(int(BASE_WIDTH * 0.7 * self.scale), int(BASE_HEIGHT * 0.7 * self.scale))

    def _apply_font_scaling(self):
        """
        所有 tk 内置字体按同一比例系数缩放；
        再派生一个「正文字体」＝默认字体的一半，供各栏正文与默认文本使用（标题保持原样）
        """
        for name in SCALED_FONTS:
            try:
                font = tkfont.nametofont(name)
                size = font.cget("size")
                font.configure(size=int(round(size * self.scale)))
            except Exception:
                continue

        default = tkfont.nametofont("TkDefaultFont")
        self.body_font = default.copy()
        self.body_font.configure(size=int(round(default.cget("size") * 0.5)))

        # 标题字体：固定 12 号、斜体（列标题用）
        self.title_font = default.copy()
        self.title_font.configure(size=12)

    # ================= 构建 =================
    def _build_topbar(self):
        # 空状态栏：先留白，后续可往里放状态文本
        bar = tk.Frame(self.root, bg=TOPBAR_BG, height=int(34 * self.scale))
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)

    def _build_body(self):
        body = tk.Frame(self.root, bg=PANEL_BG)
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=2, uniform="cols")
        body.grid_columnconfigure(1, weight=2, uniform="cols")
        body.grid_columnconfigure(2, weight=6, uniform="cols")
        body.grid_rowconfigure(0, weight=1)

        shell = self._column_shell(body, "session", 0)
        self.session_area = ScrollArea(shell)
        self.session_area.outer.pack(fill="both", expand=True)

        shell = self._column_shell(body, "mod", 1)
        self.mod_area = ScrollArea(shell)
        self.mod_area.outer.pack(fill="both", expand=True)

        shell = self._column_shell(body, "mod运行log", 2)
        self.log_text = tk.Text(
            shell,
            wrap="word",
            bg=PANEL_BG,
            fg=TEXT_MAIN,
            relief="flat",
            bd=0,
            state="disabled",
            padx=8,
            pady=6,
            font=self.body_font,
        )
        log_scroll = tk.Scrollbar(shell, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side="right", fill="y")
        self.log_text.pack(side="left", fill="both", expand=True)

    def _column_shell(self, parent, title: str, col: int):
        wrap = tk.Frame(parent, bg=PANEL_BG, highlightthickness=1, highlightbackground=LINE, bd=0)
        padx = (6, 3) if col == 0 else ((3, 6) if col == 2 else 3)
        wrap.grid(row=0, column=col, sticky="nsew", padx=padx, pady=6)
        tk.Label(
            wrap, text=title, bg=HEADER_BG, fg=TEXT_MAIN, pady=6,
            font=self.title_font, anchor="w", justify="left",
        ).pack(fill="x", padx=8)
        return wrap

    # ================= 刷新 =================
    def start(self):
        """非阻塞：把窗口先画出来（主循环留给 run()）"""
        self.root.update()

    def run(self):
        """阻塞：进入 GUI 主循环（替代 main.py 里的 input() 阻塞）"""
        self.root.after(self.poll_ms, self._refresh)
        self.root.mainloop()

    def close(self):
        try:
            if self.on_close:
                self.on_close()
        except Exception as err:
            logging.warning(f"前端关闭回调异常: {err}")
        try:
            self.root.quit()
            self.root.destroy()
        except tk.TclError:
            pass

    def _refresh(self):
        self._render_all()
        self.root.after(self.poll_ms, self._refresh)

    def _render_all(self):
        sessions = self.data_source.sessions()

        # 选中的会话已被注销 → 清空选择
        if self.selected_session_id and self.selected_session_id not in sessions:
            self.selected_session_id = None
            self.selected_mod_id = None

        self._render_sessions(sessions)

        mods = self.data_source.mods(self.selected_session_id) if self.selected_session_id else {}
        if self.selected_mod_id and self.selected_mod_id not in mods:
            self.selected_mod_id = None

        self._render_mods(mods)
        self._render_logs(mods)

    # ================= session 栏 =================
    def _render_sessions(self, sessions: dict):
        signature = (tuple(sessions.keys()), self.selected_session_id)
        if signature == self._session_sig:
            return
        self._session_sig = signature

        self.session_area.clear()
        if not sessions:
            self._placeholder(self.session_area.inner, "暂无会话（等待游戏连接）")
            return

        for index, (session_id, info) in enumerate(sessions.items()):
            background = ROW_BLUE if index % 2 == 0 else ROW_WHITE
            self._session_row(self.session_area.inner, session_id, info, background)

    def _session_row(self, parent, session_id: str, info: dict, background: str):
        row = tk.Frame(parent, bg=background, cursor="hand2")
        row.pack(fill="x")

        label = tk.Label(
            row, text=session_id, bg=background, fg=TEXT_MAIN, anchor="w",
            padx=12, pady=7, font=self.body_font,
        )
        label.pack(fill="x")

        for widget in (row, label):
            widget.bind("<Button-1>", lambda _event, sid=session_id: self._select_session(sid))

        tk.Frame(parent, bg=LINE, height=1).pack(fill="x")

        # 选中行 → 在它下方展开详情（"下拉文本框"效果）
        if session_id == self.selected_session_id:
            self._detail_box(parent, info)

    def _select_session(self, session_id: str):
        # 再次点击同一行 = 收起
        self.selected_session_id = None if session_id == self.selected_session_id else session_id
        self.selected_mod_id = None
        self._session_sig = None
        self._mod_sig = None
        self._render_all()

    # ================= mod 栏 =================
    def _render_mods(self, mods: dict):
        signature = (
            self.selected_session_id,
            tuple((mod_id, bool(body.get("enabled"))) for mod_id, body in mods.items()),
            self.selected_mod_id,
        )
        if signature == self._mod_sig:
            return
        self._mod_sig = signature

        self.mod_area.clear()
        if not self.selected_session_id:
            self._placeholder(self.mod_area.inner, "请先在左侧选中一个会话")
            return
        if not mods:
            self._placeholder(self.mod_area.inner, "该会话暂无已注册的mod")
            return

        for index, (mod_id, body) in enumerate(mods.items()):
            background = ROW_BLUE if index % 2 == 0 else ROW_WHITE
            self._mod_row(self.mod_area.inner, mod_id, body, background)

    def _mod_row(self, parent, mod_id: str, body: dict, background: str):
        info = body.get("info") or {}
        mod_name = info.get("name") or mod_id          # 行内只展示 name
        enabled = bool(body.get("enabled"))

        row = tk.Frame(parent, bg=background, cursor="hand2")
        row.pack(fill="x")

        name_label = tk.Label(
            row, text=mod_name, bg=background, fg=TEXT_MAIN, anchor="w",
            padx=12, pady=7, font=self.body_font,
        )
        name_label.pack(side="left")

        # 框选开关：先只做「状态指示」，不接入点击
        self._make_switch(row, enabled, background).pack(side="right", padx=12)

        for widget in (row, name_label):
            widget.bind("<Button-1>", lambda _event, mid=mod_id: self._select_mod(mid))

        tk.Frame(parent, bg=LINE, height=1).pack(fill="x")

        # 选中行 → 展开详情（这里再展示 id 等完整 MOD_INFO）
        if mod_id == self.selected_mod_id:
            self._detail_box(parent, info)

    def _select_mod(self, mod_id: str):
        self.selected_mod_id = None if mod_id == self.selected_mod_id else mod_id
        self._mod_sig = None
        self._render_all()

    def _make_switch(self, parent, enabled: bool, background: str):
        s = self.scale

        def k(value):
            return int(round(value * s))

        canvas = tk.Canvas(parent, width=k(36), height=k(18), bg=background, highlightthickness=0, bd=0)
        track = SWITCH_ON if enabled else SWITCH_OFF
        canvas.create_oval(k(1), k(3), k(17), k(15), fill=track, outline=track)
        canvas.create_oval(k(19), k(3), k(35), k(15), fill=track, outline=track)
        canvas.create_rectangle(k(9), k(3), k(27), k(15), fill=track, outline=track)
        knob_x = k(27) if enabled else k(9)
        knob_r = k(6)
        canvas.create_oval(knob_x - knob_r, k(3), knob_x + knob_r, k(15), fill="#FFFFFF", outline="#FFFFFF")
        return canvas

    # ================= log 栏 =================
    def _render_logs(self, mods: dict):
        signature = tuple(
            (mod_id, tuple(str(item) for item in (body.get("running_log") or [])))
            for mod_id, body in mods.items()
        )
        if signature == self._log_sig:
            return
        self._log_sig = signature

        lines = []
        for mod_id, body in mods.items():
            info = body.get("info") or {}
            mod_name = info.get("name") or mod_id
            logs = body.get("running_log") or []
            lines.append(f"┌─ {mod_name}")
            if logs:
                lines.extend(f"│  {item}" for item in logs)
            else:
                lines.append("│  (暂无运行日志)")

        content = "\n".join(lines)
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.insert("end", content)
        self.log_text.configure(state="disabled")

    # ================= 通用零件 =================
    def _placeholder(self, parent, text: str):
        tk.Label(parent, text=text, bg=PANEL_BG, fg=TEXT_SUB, pady=16, font=self.body_font).pack()

    def _detail_box(self, parent, info: dict):
        """行下方展开的详情框：通用键值渲染，后端加字段这里自动跟着显示"""
        border = tk.Frame(parent, bg=DETAIL_BORDER)
        border.pack(fill="x")

        box = tk.Frame(border, bg=DETAIL_BG)
        box.pack(fill="x", padx=1, pady=1)

        if not info:
            tk.Label(
                box, text="（无详细信息）", bg=DETAIL_BG, fg=TEXT_SUB, anchor="w", font=self.body_font,
            ).pack(fill="x", padx=16, pady=4)
            return

        for key, value in info.items():
            line = tk.Frame(box, bg=DETAIL_BG)
            line.pack(fill="x")
            tk.Label(
                line, text=str(key), bg=DETAIL_BG, fg=TEXT_SUB, width=10, anchor="w",
                font=self.body_font,
            ).pack(side="left", padx=(14, 4), pady=3)
            tk.Label(
                line, text=fmt_value(value), bg=DETAIL_BG, fg=TEXT_MAIN, anchor="w", justify="left",
                font=self.body_font,
            ).pack(side="left", padx=(0, 12), pady=3)
