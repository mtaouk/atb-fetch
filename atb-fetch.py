#!/usr/bin/env python3
import argparse
import gzip
import io
import sys
import re
import time
import tarfile
import hashlib
from pathlib import Path
from urllib.request import urlopen
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Set, Dict, Tuple

DEFAULT_URL = "https://osf.io/download/4yv85/"

def is_gzip(data: bytes) -> bool:
    return data[:2] == b"\x1f\x8b"

def md5_ok(path: Path, expected: Optional[str]) -> bool:
    if not expected or not path.exists():
        return False
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest() == expected.lower()

def download_with_retry(url: str, out: Path, expected_md5: Optional[str] = None, attempts: int = 5) -> str:
    out.parent.mkdir(parents=True, exist_ok=True)
    for i in range(attempts):
        try:
            if expected_md5 and md5_ok(out, expected_md5):
                return "cached-ok"
            with urlopen(url, timeout=120) as r:
                data = r.read()
            tmp = out.with_suffix(out.suffix + ".part")
            with open(tmp, "wb") as f:
                f.write(data)
            tmp.replace(out)
            if expected_md5 and not md5_ok(out, expected_md5):
                raise ValueError("md5 mismatch")
            return "downloaded"
        except Exception:
            if i == attempts - 1:
                raise
            time.sleep(2 ** i)
    return "failed"

def extract_selected(tar_path: Path, members_to_get: Set[str], outdir: Path, strip_components: int = 1) -> Set[str]:
    outdir.mkdir(parents=True, exist_ok=True)
    missing = set(members_to_get)
    mode = "r:xz" if tar_path.suffix.endswith("xz") else "r:*"
    with tarfile.open(tar_path, mode=mode) as tf:
        for member in tf:
            if not member.isreg():
                continue
            if member.name in missing:
                # flatten path after stripping N components
                parts = Path(member.name).parts[strip_components:]
                target_name = Path(*parts).name if parts else Path(member.name).name
                out_path = outdir / target_name
                src = tf.extractfile(member)
                if src is None:
                    continue
                with open(out_path, "wb") as dst:
                    for chunk in iter(lambda: src.read(1024 * 1024), b""):
                        if not chunk:
                            break
                        dst.write(chunk)
                missing.remove(member.name)
            if not missing:
                break
    return missing

def main():
    ap = argparse.ArgumentParser(
        description="Fetch ATB file list from OSF, optionally decompress, filter, and download-extract matches."
    )
    ap.add_argument("--url", default=DEFAULT_URL, help="OSF download URL. Default pulls latest.")
    ap.add_argument("--infile", help="Path to local metadata TSV or TSV.gz. Skips download if set.")
    ap.add_argument("--out", default="file_list.all.latest.tsv.gz", help="Where to save the downloaded metadata.")
    ap.add_argument("--decompress", action="store_true", help="Also write an uncompressed .tsv next to the metadata.")
    ap.add_argument("--species", help="Case-insensitive regex to match species or genus.")
    ap.add_argument("--save-filtered", help="Path to save filtered TSV (.gz ok).")
    ap.add_argument("--preview", type=int, default=5, help="Show first N matches of filtered TSV.")
    # Option B controls
    ap.add_argument("--run-downloads", action="store_true", help="Download tarballs and extract matching FASTA files.")
    ap.add_argument("--jobs", type=int, default=4, help="Concurrent downloads. Default: 4")
    ap.add_argument("--output-dir", default="assemblies", help="Directory to write extracted FASTA files.")
    ap.add_argument("--delete-tars", action="store_true", help="Delete downloaded tar.xz files after extraction. Default: keep")
    ap.add_argument("--strip-components", type=int, default=1, help="tar --strip-components value for extraction.")
    ap.add_argument("--dry-run", action="store_true", help="Show planned downloads/extractions without performing them")
    args = ap.parse_args()

    out_path = Path(args.out)
    required_cols = ["sample", "species_sylph", "species_miniphy", "tar_xz", "tar_xz_url", "filename_in_tar_xz"]

    # Get metadata bytes
    if args.infile:
        infile_path = Path(args.infile)
        print(f"Reading existing metadata from {infile_path}")
        data = infile_path.read_bytes()
        # Header check
        if is_gzip(data):
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as gz:
                header_line = gz.readline().decode("utf-8", errors="replace").strip()
        else:
            header_line = data.split(b"\n", 1)[0].decode("utf-8", errors="replace").strip()
        header_cols = header_line.split("\t")
        missing_req = [c for c in required_cols if c not in header_cols]
        if missing_req:
            print(f"Local file missing required columns {missing_req}. Downloading from {args.url} instead.")
            with urlopen(args.url, timeout=360) as r:
                data = r.read()
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "wb") as f:
                f.write(data)
            print(f"Saved {out_path} ({len(data)} bytes)")
        else:
            out_path = infile_path
    else:
        print(f"Downloading {args.url} as {out_path}")
        with urlopen(args.url, timeout=360) as r:
            data = r.read()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(data)
        print(f"Saved {out_path} ({len(data)} bytes)")

    # Optional plain TSV copy
    if args.decompress:
        if is_gzip(data):
            tsv_path = out_path.with_suffix("") if out_path.suffix == ".gz" else out_path.with_suffix(".tsv")
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as gz, open(tsv_path, "wb") as out_tsv:
                out_tsv.write(gz.read())
            print(f"Also wrote uncompressed TSV -> {tsv_path}")
        else:
            print("Note: download does not look gzipped, skipping decompression.", file=sys.stderr)

    # Filtering
    kept = []
    colmap: Dict[str, int] = {}
    header = ""
    if args.species:
        if is_gzip(data):
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as gz:
                tsv_text = gz.read().decode("utf-8", errors="replace")
        else:
            tsv_text = data.decode("utf-8", errors="replace")

        lines = tsv_text.splitlines()
        if not lines:
            print("Empty file?")
            return

        header = lines[0]
        cols = header.split("\t")
        colmap = {name: i for i, name in enumerate(cols)}

        # helpful but not fatal
        need = ["tar_xz", "tar_xz_url", "filename_in_tar_xz"]
        missing = [c for c in need if c not in colmap]
        if missing:
            print(f"Warning: missing columns: {missing}", file=sys.stderr)

        pattern = re.compile(args.species, flags=re.IGNORECASE)
        preview_left = args.preview

        for line in lines[1:]:
            fields = line.split("\t")
            vals = []
            if "species_sylph" in colmap:
                vals.append(fields[colmap["species_sylph"]])
            if "species_miniphy" in colmap:
                vals.append(fields[colmap["species_miniphy"]])

            if any(pattern.search(v or "") for v in vals):
                kept.append(line)
                if preview_left > 0:
                    print(line)
                    preview_left -= 1

        print(f"\nMatched {len(kept)} rows")

        if args.save_filtered:
            save_path = Path(args.save_filtered)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            body = "\n".join([header] + kept) + "\n"
            if save_path.suffix == ".gz":
                with gzip.open(save_path, "wt") as f:
                    f.write(body)
            else:
                save_path.write_text(body)
            print(f"Saved filtered metadata to {save_path}")

    # Download and extract
    if args.run_downloads:
        if not kept:
            print("No filtered rows to download. Provide --species or skip --run-downloads.")
            return
        if not colmap:
            print("Internal error: colmap not set.")
            return

        rows = [r.split("\t") for r in kept]
        ix_tar   = colmap["tar_xz"]
        ix_url   = colmap["tar_xz_url"]
        ix_inTar = colmap["filename_in_tar_xz"]
        ix_md5   = colmap.get("tar_xz_md5", None)

        plan: Dict[Tuple[str, str], Set[str]] = {}
        md5_map: Dict[str, str] = {}
        for f in rows:
            key = (f[ix_tar], f[ix_url])
            plan.setdefault(key, set()).add(f[ix_inTar])
            if ix_md5 is not None:
                md5_val = f[ix_md5]
                if md5_val:
                    md5_map[f[ix_tar]] = md5_val

        outdir = Path(args.output_dir)
        tars_dir = outdir / "_tars"
        tars_dir.mkdir(parents=True, exist_ok=True)

        print(f"Planned download of {len(plan)} tarballs with {args.jobs} jobs")

        if args.dry_run:
            print("\n[DRY RUN] Listing planned downloads and members:")
            for (tarname, url), members in plan.items():
                print(f"Tarball: {tarname}")
                print(f"  URL: {url}")
                if tarname in md5_map:
                    print(f"  MD5: {md5_map[tarname]}")
                for m in sorted(members):
                    print(f"    {m}")
            print("\n[DRY RUN] No downloads or extractions performed.")
            return

        # Actually download tarballs
        with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as ex:
            futs = {}
            for (tarname, url), _members in plan.items():
                tar_path = tars_dir / tarname
                futs[ex.submit(download_with_retry, url, tar_path, md5_map.get(tarname))] = (tarname, tar_path)
            for fut in as_completed(futs):
                tarname, tar_path = futs[fut]
                status = fut.result()
                print(f"{tarname}: {status}")

        # Extract targets
        misses_total = []
        for (tarname, _url), members in plan.items():
            tar_path = tars_dir / tarname
            missing = extract_selected(tar_path, members, outdir, strip_components=args.strip_components)
            if missing:
                print(f"Warning: {tarname} missing {len(missing)} expected members", file=sys.stderr)
                misses_total.extend(list(missing))
            if args.delete_tars:
                try:
                    tar_path.unlink()
                except Exception:
                    pass

        if misses_total:
            print(f"Finished with {len(misses_total)} missing members. See warnings above.", file=sys.stderr)
        else:
            print("All done extracting.")

if __name__ == "__main__":
    main()
