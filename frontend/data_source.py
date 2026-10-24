import logging


class FrontendDataSource:
    """
    前端数据源（只读快照层）

    职责：
    把 Socks5Manager / ModManager 的内部状态，转成前端可安全使用的「纯数据」。
    GUI 线程只碰这里的返回值，绝不直接引用 Session / ModRunTime 对象，
    避免和 socks5 工作线程的注册/注销发生跨线程竞态。
    """

    def __init__(self, socks5_manager):
        self.socks5_manager = socks5_manager

    # ================= 内部 =================
    @property
    def _mods_manager(self):
        return getattr(self.socks5_manager, "mods_manager", None)

    @staticmethod
    def _plain(mapping: dict) -> dict:
        """浅拷贝一层：值都是标量/字符串，复制后与内部状态解耦"""
        return {key: value for key, value in dict(mapping).items()}

    # ================= 对外 =================
    def sessions(self) -> dict:
        """
        {session_id: {字段名: 值}}

        字段名由后端决定，前端只做「通用键值渲染」——
        后端将来给 list_having_session() 增加字段，这里无需改动。
        """
        try:
            raw = self.socks5_manager.list_having_session() or {}
            return {sid: self._plain(info) for sid, info in raw.items()}
        except Exception as err:
            logging.warning(f"前端读取会话列表失败: {err}")
            return {}

    def mods(self, session_id: str | None) -> dict:
        """
        {mod_id: {"enabled": bool, "info": dict, "running_log": list}}
        """
        if not session_id:
            return {}

        mods_manager = self._mods_manager
        if mods_manager is None:
            return {}

        # 首选：ModManager 暴露的快照接口
        try:
            snapshot = mods_manager.list_session_mod_state(session_id)
            if snapshot:
                return {
                    mod_id: {
                        "enabled": bool(body.get("enabled")),
                        "info": dict(body.get("info") or {}),
                        "running_log": list(body.get("running_log") or []),
                    }
                    for mod_id, body in snapshot.items()
                }
        except Exception as err:
            logging.warning(f"前端读取会话 {session_id} 的mod状态失败: {err}")

        # 兜底：快照接口尚未补齐 return 时，直接读状态机表（同锁只读复制）
        return self._mods_fallback(mods_manager, session_id)

    def set_mod_enabled(self, session_id: str, mod_id: str, enabled: bool) -> tuple[bool, str]:
        """
        切换某个 mod 的开关，返回 (是否成功, 给状态栏看的说明)。

        开关动作由 mod 实例自己实现（instance.start/stop 内部改 enabled、调初始化并自行回滚），
        这里只负责选对入口：
          1. 优先走 ModManager.start_mod_in_session / stop_mod_in_session（后端统一入口，含锁）
          2. 后端没提供时直接调实例的 start/stop
        绝不再走 ModRunTime.start/stop —— 它写死了 `enabled_init` 这个名字，与实例实现容易脱节。
        """
        if not session_id or not mod_id:
            return False, "参数不完整"

        mods_manager = self._mods_manager
        if mods_manager is None:
            return False, "mod管理器不可用"

        runtime = self._get_runtime(mods_manager, session_id, mod_id)
        if runtime is None:
            return False, "mod不存在（会话可能已注销）"

        instance = getattr(runtime, "instance", None)
        if instance is None:
            return False, "mod实例缺失"

        if enabled and runtime.is_enabled():
            return True, "已处于开启状态"

        try:
            if enabled:
                entry = getattr(mods_manager, "start_mod_in_session", None)
                actions = entry(session_id, mod_id) if callable(entry) else instance.start()
                count = len(actions) if isinstance(actions, (list, tuple)) else 0
                return True, f"已开启（初始化动作 {count} 条）"

            entry = getattr(mods_manager, "stop_mod_in_session", None)
            if callable(entry):
                entry(session_id, mod_id)
            else:
                instance.stop()
            return True, "已关闭"
        except Exception as err:
            # 实例 start 成功置位后若初始化抛错，实例内部应已回滚；这里再兜一层，避免假开启
            try:
                instance.stop()
            except Exception:
                pass
            return False, f"操作失败: {err}"

    def _get_runtime(self, mods_manager, session_id: str, mod_id: str):
        """在锁内取一次 ModRunTime 引用（锁外再调用它，避免持锁跑业务）"""
        states = getattr(mods_manager, "session_mods_state", None)
        if states is None:
            return None

        lock = getattr(mods_manager, "mod_lock", None)
        if lock is None:
            return (states.get(session_id) or {}).get(mod_id)
        with lock:
            return (states.get(session_id) or {}).get(mod_id)

    def _mods_fallback(self, mods_manager, session_id: str) -> dict:
        states = getattr(mods_manager, "session_mods_state", None)
        if states is None:
            return {}

        lock = getattr(mods_manager, "mod_lock", None)
        result = {}

        def build():
            for mod_id, runtime in (states.get(session_id) or {}).items():
                instance = getattr(runtime, "instance", None)
                result[mod_id] = {
                    "enabled": bool(runtime.is_enabled()),
                    "info": dict(getattr(instance, "MOD_INFO", {}) or {}),
                    "running_log": list(getattr(runtime, "running_log", []) or []),
                }

        if lock is not None:
            with lock:
                build()
        else:
            build()

        return result
