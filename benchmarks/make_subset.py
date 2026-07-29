"""Build a smaller DwCA from a GBIF download, for benchmarking at a lower scale.

Truncates occurrence.txt to the first N data rows and filters verbatim.txt and
multimedia.txt down to the extension rows that reference those core ids, so all
three files shrink together. Everything else (meta.xml, metadata.xml, the
dataset/ directory) is copied through unchanged.

Both GBIF extension files use gbifID as their first column, which is what the
core id column holds, so a simple first-column membership test is enough.

Usage:
    uv run python benchmarks/make_subset.py <source.zip> <dest.zip> <n_rows>
"""

import sys
import zipfile

CORE = "occurrence.txt"
EXTENSIONS = ("verbatim.txt", "multimedia.txt")


def _lines(zf: zipfile.ZipFile, name: str):
    with zf.open(name) as raw:
        for line in raw:
            yield line


def main(source: str, dest: str, n_rows: int) -> int:
    with zipfile.ZipFile(source) as src:
        names = set(src.namelist())

        # Pass 1: truncate the core file, remembering which ids survived.
        kept_ids: set[bytes] = set()
        core_out: list[bytes] = []
        for index, line in enumerate(_lines(src, CORE)):
            if index == 0:  # header line (meta.xml declares ignoreHeaderLines=1)
                core_out.append(line)
                continue
            if len(kept_ids) >= n_rows:
                break
            kept_ids.add(line.split(b"\t", 1)[0])
            core_out.append(line)
        print(f"{CORE}: kept {len(kept_ids)} data rows")

        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as out:
            out.writestr(CORE, b"".join(core_out))

            # Pass 2: keep only extension rows pointing at a surviving core id.
            for ext in EXTENSIONS:
                if ext not in names:
                    continue
                kept = 0
                chunks: list[bytes] = []
                for index, line in enumerate(_lines(src, ext)):
                    if index == 0:
                        chunks.append(line)
                        continue
                    if line.split(b"\t", 1)[0] in kept_ids:
                        chunks.append(line)
                        kept += 1
                out.writestr(ext, b"".join(chunks))
                print(f"{ext}: kept {kept} rows")

            # Everything else copied verbatim.
            for name in src.namelist():
                if name in (CORE,) + EXTENSIONS:
                    continue
                out.writestr(name, src.read(name))

    return 0


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1], sys.argv[2], int(sys.argv[3])))
