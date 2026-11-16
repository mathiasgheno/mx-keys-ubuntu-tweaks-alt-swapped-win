#!/usr/bin/python3
"""Install personal acute+C compose rules without changing system files."""
from pathlib import Path
import shutil

RULES = '\n# MX Keys: Portuguese cedilla composition\n<dead_acute> <c> : "ç" ccedilla\n<dead_acute> <C> : "Ç" Ccedilla\n'


def install(path):
    existing = path.read_text() if path.exists() else 'include "%L"\n'
    if RULES.strip() in existing:
        return False
    if path.exists():
        backup = path.with_name(path.name + '.before-cedilla')
        if backup.exists():
            raise FileExistsError(f'Backup already exists: {backup}; inspect it before retrying')
        shutil.copy2(path, backup)
    path.write_text(existing.rstrip() + '\n' + RULES)
    return True


if __name__ == '__main__':
    changed = install(Path.home() / '.XCompose')
    print('Cedilla rules installed.' if changed else 'Cedilla rules already installed.')
    print('Reopen applications; log out and back in if needed.')
