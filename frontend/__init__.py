from .data_source import FrontendDataSource
from .panel import FrontendPanel


def get_frontend(socks5_manager, title: str = "火影协议前端", on_close=None, poll_ms: int = 400):
    """
    构建前端面板（只读快照 + 展示，不阻塞）

    :param socks5_manager: 已装配好的 Socks5Manager（面板从它读取会话/mod状态）
    :param title:          窗口标题
    :param on_close:       点击「关闭」或关窗时的回调（一般用来停 socks5 / proxy）
    :param poll_ms:        轮询周期（毫秒），越小越实时、越费一点主线程
    """
    return FrontendPanel(
        data_source=FrontendDataSource(socks5_manager),
        title=title,
        on_close=on_close,
        poll_ms=poll_ms,
    )


__all__ = ["FrontendDataSource", "FrontendPanel", "get_frontend"]
