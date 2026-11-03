#!/usr/bin/env python3
"""
Download the Isaac Sim / SimReady assets the Task 5 scene uses (~120 MB) into a local folder, so jobs on cluster
compute nodes do not need internet access. Standard library only.

  python3 fetch_assets.py /scratch/gilbreth/$USER/task5/isaac_assets
  python3 build_task5_scene.py --assets-root /scratch/gilbreth/$USER/task5/isaac_assets
"""
import concurrent.futures as cf
import os
import re
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asset_list import ASSETS, DEFAULT_ASSETS_ROOT, EXTRA_FOLDERS  # noqa: E402

BUCKET = DEFAULT_ASSETS_ROOT + "/"


def list_keys(prefix):
    keys, token = [], None
    while True:
        q = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
        if token:
            q["continuation-token"] = token
        xml = urllib.request.urlopen(BUCKET + "?" + urllib.parse.urlencode(q), timeout=60).read().decode()
        keys += re.findall(r"<Key>([^<]+)</Key>", xml)
        m = re.search(r"<NextContinuationToken>([^<]+)", xml)
        if not m:
            return keys
        token = m.group(1)


def fetch(key, root):
    out = os.path.join(root, key)
    if os.path.exists(out) and os.path.getsize(out) > 0:
        return 0
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out + ".part"
    urllib.request.urlretrieve(BUCKET + urllib.parse.quote(key), tmp)
    os.replace(tmp, out)
    return os.path.getsize(out)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    root = os.path.abspath(sys.argv[1])
    keys = []
    folders = [path.rsplit("/", 1)[0] + "/" for path in ASSETS.values()] + EXTRA_FOLDERS
    for folder in folders:
        keys += [k for k in list_keys(folder) if not k.endswith("/") and "/.thumbs/" not in k]
    with cf.ThreadPoolExecutor(16) as ex:
        sizes = list(ex.map(lambda k: fetch(k, root), keys))
    print(f"{len(keys)} files in {root} ({sum(sizes) / 1e6:.0f} MB downloaded now)")
