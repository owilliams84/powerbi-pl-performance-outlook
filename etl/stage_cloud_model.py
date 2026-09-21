"""Stage a copy of the semantic model whose partitions read the CSVs over HTTPS.

    python etl/stage_cloud_model.py <base url> <output folder>

The committed model reads `data/*.csv` from the local disk through the `Data Folder` parameter,
which is right for Desktop and useless in the Power BI Service: a local path needs an on-premises
gateway. The source dataset is "Data files (c) Original Authors", so the CSVs cannot go on a public
host the way the other reports' data does. They can sit somewhere private that the Service can
reach with an organisational sign-in - OneDrive for work or SharePoint - and this script writes the
model that reads them from there.

Every partition calls Web.Contents on the same root with the file in RelativePath, so the
Service sees one data source and asks for one sign-in rather than seven. The root is the site's
REST endpoint, `<site>/_api/web`, and each file is fetched as
`GetFileByServerRelativePath(decodedurl='...')/$value`. That root matters: when credentials are
saved the Service tests them with a GET on the root, and it has to answer 200 to a bearer token.
The site's home page does not (the test failed with "The credentials provided for the Web source
are invalid", status 400), and a bare folder URL serves nothing at all. `_api/web` does.

The base URL is an argument, not a constant, so nobody's tenant ends up in the repository.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "PL Performance and Outlook.SemanticModel"
LOCAL = re.compile(r'File\.Contents\(#"Data Folder" & "\\([A-Za-z0-9_]+\.csv)"\)')


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    base, out = sys.argv[1].rstrip("/"), Path(sys.argv[2])
    if not base.lower().startswith("https://"):
        raise SystemExit("the base URL must be https")
    site = re.match(r"https://[^/]+(?:/(?:personal|sites|teams)/[^/]+)?", base, re.I).group(0)
    folder = quote(base[len(site):].strip("/"), safe="/%")     # spaces in a OneDrive path become %20
    site_path = quote(re.sub(r"^https://[^/]+", "", site), safe="/%")   # /personal/<user>
    if "'" in folder + site_path:
        raise SystemExit("an apostrophe in the path would break the REST call; rename the folder")
    if out.exists():
        raise SystemExit(f"{out} already exists - stage into a fresh folder")
    shutil.copytree(MODEL, out, ignore=shutil.ignore_patterns(".pbi", "*.abf", "localSettings.json"))

    swapped = []
    for tmdl in sorted((out / "definition" / "tables").glob("*.tmdl")):
        text = tmdl.read_text(encoding="utf-8")
        new, n = LOCAL.subn(
            lambda m: (f'Web.Contents("{site}/_api/web", [RelativePath="GetFileByServerRelativePath('
                       f"decodedurl='{site_path}/{folder}/{m.group(1)}')/$value\"])"), text)
        if n:
            tmdl.write_text(new, encoding="utf-8", newline="\n")
            swapped += LOCAL.findall(text)
    expected = sorted(p.name for p in (ROOT / "data").glob("*.csv"))
    if sorted(swapped) != expected:
        raise SystemExit(f"partitions swapped {sorted(swapped)} but data/ holds {expected}")
    print(f"{len(swapped)} partitions now read {site}/_api/web -> {site_path}/{folder}/<file>.csv")
    print(f"staged in {out}")


if __name__ == "__main__":
    main()
