"""Print size and sha256 of every file in a folder (non-recursive).  python -I hash_dir.py <folder> [more folders]"""
import hashlib
import os
import sys

for folder in sys.argv[1:]:
    for name in sorted(os.listdir(folder)):
        p = os.path.join(folder, name)
        if not os.path.isfile(p):
            continue
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 22), b""):
                h.update(chunk)
        print(f"{h.hexdigest()}  {os.path.getsize(p):>11d}  {name}")
