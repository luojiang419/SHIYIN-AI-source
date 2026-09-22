import sys
from pathlib import Path

if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __name__ == '__main__':
    if '--service' in sys.argv:
        sys.argv.remove('--service')
        from distribution.startup import run_service
        run_service()
    else:
        from distribution.launcher import main
        main()
