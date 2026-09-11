"""复用局部Lab诊断，比较面料端口原结果与原色锁定复测；不修改图像颜色。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('color_audit', ROOT / 'tools/pose-replicate-color-audit.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
audit.ROOT = ROOT / '输出/一键复刻面料细节-20260911'
audit.CASES = [
    ('服装参考', 'garment.png', audit.REFERENCE_BOXES),
    ('面料端口首次结果', 'result.png', audit.TARGET_BOXES),
    ('原色锁定复测', 'color-lock/result.png', audit.TARGET_BOXES),
    ('二次仅服装校色', 'color-correction/result.png', audit.TARGET_BOXES),
]
if __name__ == '__main__':
    audit.main()
