# atb-fetch

Fetch and filter [**AllTheBacteria**](https://allthebacteria.org/)
genome assemblies by species, with optional download and extraction of
compressed tar archives.

------------------------------------------------------------------------

## About AllTheBacteria (ATB)

[AllTheBacteria (ATB)](https://osf.io/4yv85/) is a public collection of
over two million bacterial genome assemblies.\
To keep the dataset manageable in size, assemblies are packaged into
`.tar.xz` archives using **Miniphy** compression.\
Each archive contains up to \~4000 gzipped FASTA files.

This compression is essential — for example, in release 0.2: - All
assemblies as individual gzipped FASTA files: **\~3.1 TB** - Same
assemblies as `.tar.xz` batches: **\~89 GB**

However, the downside is: - You must **identify** which archive holds
your genome(s) - **wget** the whole `.tar.xz` batch - **tar** out the
exact FASTA(s) you care about

### The ATB Metadata

The file `file_list.all.latest.tsv.gz` contains everything you need to
find and download assemblies: - `sample` – INSDC sample accession -
`species_sylph` – species name from Sylph - `species_miniphy` –
Miniphy’s species name - `filename_in_tar_xz` – file path inside the
`.tar.xz` - `tar_xz` – name of the `.tar.xz` file containing the
assembly - `tar_xz_url` – OSF download URL - `tar_xz_md5` – checksum for
file integrity - `tar_xz_size_MB` – file size in MB

You can technically do this manually with a combination of `awk`,
`wget`, and `tar`, but it’s time-consuming. It’s even worse when you
want **everything for a whole species or genus**, since those assemblies
are often scattered across many different archives.

## How this tool helps

This script **automates** the whole process using only Python’s standard
library:

-   Give it a **species or genus name** (regex, case-insensitive) and it
    searches both `species_sylph` and `species_miniphy` columns.
-   Finds all matching rows across the full ATB metadata.
-   Downloads only the tarballs that actually contain matches.
-   Extracts only the matching FASTA files from each tarball.
-   Lets you preview or save the filtered metadata before downloading so
    you can sanity-check the results.

💡 **Tip:**\
Filtering uses **both** `species_sylph` and `species_miniphy` for regex
matches.\
It’s worth saving the filtered metadata (`--save-filtered`) and checking
it manually before running large downloads.

## Installation

Clone the repo:

```         
git clone <https://github.com/yourusername/atb-fetch.git> 
cd atb-fetch
```

The script only uses Python standard library modules — no extra installs
needed. Tested with Python 3.8+.

## Usage

```         
# Example: filter for Serratia, preview matches only
python atb-fetch.py --species "serratia" --dry-run

# Example: filter for Serratia and download/extract assemblies
python atb-fetch.py --species "serratia" --run-downloads
```

### Options

| Option               | Argument           | Description                                                                                                                                      |
|----------------------|--------------------|--------------------------------------------------------------------------------------------------------------------------------------------------|
| `-h`, `--help`       | *(none)*           | Show the help message with a full list of options, then exit.                                                                                    |
| `--url`              | `URL`              | OSF download URL for the AllTheBacteria metadata file. Defaults to the latest version. You can override if you have a different source.          |
| `--infile`           | `INFILE`           | Path to a **local** metadata TSV or TSV.gz file. Skips downloading from OSF if provided. Useful if you already have the file.                    |
| `--out`              | `OUT`              | Path to save the downloaded metadata file. Default: `file_list.all.latest.tsv.gz`.                                                               |
| `--decompress`       | *(flag)*           | Also write an **uncompressed** `.tsv` copy next to the downloaded `.gz` file.                                                                    |
| `--species`          | `SPECIES`          | Case-insensitive **regex** to match species or genus names in the metadata. Matches both `species_miniphy` and `species_sylph` columns.          |
| `--save-filtered`    | `SAVE_FILTERED`    | Path to save the filtered metadata (can be `.gz` or `.tsv`). Handy for checking what was matched.                                                |
| `--preview`          | `PREVIEW`          | Show the first **N** matching rows from the filtered metadata. Default: `5`.                                                                     |
| `--run-downloads`    | *(flag)*           | Actually download the matching tarballs and extract their FASTA files. Without this flag, the script only filters metadata.                      |
| `--jobs`             | `JOBS`             | Number of concurrent downloads. Default: `4`. Increase for faster downloads if your internet is good.                                            |
| `--output-dir`       | `OUTPUT_DIR`       | Directory where extracted FASTA files will be saved.                                                                                             |
| `--delete-tars`      | *(flag)*           | Delete the downloaded `.tar.xz` files after extraction. Default: keep them.                                                                      |
| `--strip-components` | `STRIP_COMPONENTS` | Number of leading path components to strip during tar extraction (like `tar --strip-components`). Useful if you want a flatter folder structure. |
| `--dry-run`          | *(flag)*           | Show which tarballs and FASTA files **would** be downloaded and extracted without actually doing it. Great for testing your filters first.       |

### Notes

-   **Metadata source:** [AllTheBacteria OSF](https://osf.io/4yv85/)
-   Tar archives use `miniphy` compression (\~35× smaller than gzipped
    FASTA)
-   You must download and extract to access individual assemblies
-   Filtering uses case-insensitive regular expressions, so `"serratia"`
    will match `"Serratia marcescens"` and `"Serratia sp."`
-   The script checks both the `species_miniphy` and `species_sylph`
    columns for regex matches — you may want to use `--save-filtered`
    and review the output TSV to confirm the results match your intent
-   The script only uses Python’s standard library — no extra installs
    needed
