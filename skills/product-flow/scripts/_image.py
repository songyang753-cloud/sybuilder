"""Decode evidence images; an extension or PNG header is never proof of an image."""
from pathlib import Path
import warnings


def validate_image(path):
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError('UNABLE: install the pinned Pillow dependency in requirements.txt') from exc
    path = Path(path)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(path) as image:
                if image.width <= 0 or image.height <= 0:
                    raise ValueError('empty image')
                image.verify()
            with Image.open(path) as image:
                image.load()
                return image.size
    except (OSError, ValueError, SyntaxError, Warning, Image.DecompressionBombError) as exc:
        raise ValueError('invalid evidence image: %s (%s)' % (path.name, exc)) from exc


if __name__ == '__main__':
    import sys
    if '--self-test' in sys.argv:
        import runpy
        from pathlib import Path
        tests = runpy.run_path(str(Path(__file__).resolve().parents[3] / 'scripts/test-remediation-contracts.py'))
        sys.exit(tests['main']('image'))
