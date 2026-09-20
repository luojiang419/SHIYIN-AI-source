"""共享教程侧栏，供离线培训套件中的页面内嵌使用。"""
from pathlib import Path


TOOLS = Path(__file__).resolve().parent


def build_sidebar(active: str, batch_href: str, universal_href: str, video_href: str) -> str:
    items = [
        ('batch', '01', '批量换款', '换款与一键复刻', batch_href),
        ('universal', '02', '全能模式', '标准产品图与 Lookbook', universal_href),
        ('video', '03', '视频生成', '分镜、资产与深度视频', video_href),
    ]
    links = ''.join(
        f'<a href="{href}" title="{title}" aria-current="{("page" if key == active else "false")}">'
        f'<span class="tutorial-menu-index">{index}</span>'
        f'<span class="tutorial-sidebar-copy"><b>{title}</b><small>{subtitle}</small></span></a>'
        for key, index, title, subtitle, href in items
    )
    return (
        '<aside class="tutorial-sidebar" id="tutorialSidebar">'
        '<div class="tutorial-sidebar-brand"><span class="tutorial-brand-mark">S</span>'
        '<span class="tutorial-sidebar-copy"><strong>拾影教程</strong><small>SHIYIN TRAINING</small></span></div>'
        f'<nav class="tutorial-menu" aria-label="教程导航">{links}</nav>'
        '<p class="tutorial-sidebar-copy tutorial-sidebar-hint">整套教程可离线复制使用</p>'
        '</aside><button class="tutorial-sidebar-toggle" id="tutorialSidebarToggle" '
        'aria-controls="tutorialSidebar" aria-expanded="true" title="折叠教程导航">'
        '<span class="tutorial-toggle-expanded" aria-hidden="true">‹</span>'
        '<span class="tutorial-toggle-collapsed" aria-hidden="true">›</span>'
        '<span class="sr-only">折叠教程导航</span></button>'
        '<button class="tutorial-sidebar-scrim" id="tutorialSidebarScrim" aria-label="关闭教程导航"></button>'
    )


def sidebar_css() -> str:
    return (TOOLS/'training-tutorial-sidebar.css').read_text(encoding='utf-8')


def sidebar_js() -> str:
    return (TOOLS/'training-tutorial-sidebar.js').read_text(encoding='utf-8')
