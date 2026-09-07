"""统一解析、润色、跨模型迁移的提示词规范注册表。"""
from pathlib import Path

PROFILES = {
    'seedance': {'title': 'Seedance 2.0 / Fast', 'limit': 2000,
        'source': 'https://www.volcengine.com/docs/82379/2222480?lang=zh', 'kind': 'official-document-adapter'},
    'hailuo': {'title': 'MiniMax Hailuo 2.3', 'limit': 2000,
        'source': 'https://github.com/MiniMax-AI/skills/blob/main/skills/frontend-dev/references/minimax-video-guide.md', 'kind': 'official-skill-adapter'},
    'wan': {'title': 'Wan 2.6', 'limit': 1500,
        'source': 'https://help.aliyun.com/zh/model-studio/text-to-video-prompt', 'kind': 'official-document-adapter'},
    'happyhorse': {'title': 'HappyHorse', 'limit': 2000,
        'source': 'https://github.com/modelstudioai/awesome-happyhorse-prompts/blob/main/happyhorse-prompt-craft-SKILL.md', 'kind': 'published-skill-adapter'},
    'kling-linkfox': {'title': 'LinkFox 可灵 Omni / 2.6', 'limit': 2000,
        'source': 'https://kling.ai/quickstart/klingai-video-3-model-user-guide', 'kind': 'official-document-adapter'},
}


def registered_profile(provider: str, model: str) -> str:
    name = f'{provider} {model}'.lower()
    if 'h3' in name:
        return 'minimax-h3'
    if 'kling' in name or '可灵' in name:
        return 'kling-linkfox' if provider == 'linkfox' else 'kling-cli'
    if any(word in name for word in ('hailuo', '海螺', 'minimax')):
        return 'hailuo'
    if any(word in name for word in ('happyhorse', 'happy_horse')):
        return 'happyhorse'
    if 'wan' in name or '万相' in name:
        return 'wan'
    if any(word in name for word in ('seedance', 'jimeng', '即梦', 'doubao', 'volcengine')):
        return 'seedance'
    return 'generic'


def load_registered_skill(root: str, provider: str, model: str) -> tuple[str, str] | None:
    profile = registered_profile(provider, model)
    if profile not in PROFILES:
        return None
    path = Path(root) / 'skills' / 'video-prompt-polish' / profile / 'SKILL.md'
    # 缺失规则不能静默降级为通用提示词；安装包检查会覆盖此目录。
    return path.read_text(encoding='utf-8'), profile
