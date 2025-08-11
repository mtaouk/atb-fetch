# atb-fetch

Fetch and filter **AllTheBacteria** genome assemblies by species, with
optional download and extraction of compressed tar archives.

## Features

-   Pull the latest ATB metadata file from OSF, or use a local copy\
-   Filter assemblies by species name (case-insensitive regex)\
-   Preview matches before downloading\
-   Download only the tarballs you need\
-   Extract the exact assemblies from each tarball\
-   Optional dry-run mode to see what would be downloaded\
-   Clean up tarballs automatically after extraction

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

| Option            | Description                                            |
|-------------------|--------------------------------------------------------|
| `--species`       | Case-insensitive regex to filter species or genus      |
| `--infile`        | Use a local metadata TSV/TSV.gz instead of downloading |
| `--save-filtered` | Save filtered metadata to a file                       |
| `--run-downloads` | Actually download and extract the assemblies           |
| `--dry-run`       | Show planned downloads/extractions without doing them  |
| `--delete-tars`   | Remove tarballs after extraction                       |

### Notes

-   **Metadata source:** [AllTheBacteria OSF](https://osf.io/4yv85/)\
-   Tar archives use `miniphy` compression (\~35× smaller than gzipped
    FASTA)\
-   You must download and extract to access individual assemblies\
-   Filtering uses case-insensitive regular expressions, so `"serratia"`
    will match `"Serratia marcescens"` and `"Serratia sp."`
-   The script checks both the `species_miniphy` and `species_sylph`
    columns for regex matches — you may want to use `--save-filtered`
    and review the output TSV to confirm the results match your intent\
-   The script only uses Python’s standard library — no extra installs
    needed
