"""让 event_cleaner 可作为模块执行：python -m event_cleaner ..."""

from .cli import main
import sys

if __name__ == '__main__':
    sys.exit(main())
