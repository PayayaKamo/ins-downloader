# Instagram Media Downloader

A small command-line tool built on [instaloader](https://instaloader.github.io/) that archives
public Instagram profiles: every image of every post, carousel frames included, together with
captions, metadata and a CSV index.

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

## What it does

- Downloads all images from one or more public profiles (the whole profile, or a date range).
- Saves each carousel frame as its own file, so multi-image posts are kept in full.
- Writes a `.txt` caption and a `.json` metadata file next to every post.
- Maintains `_index.csv`, a single table describing everything downloaded so far.
- Skips files that already exist and resumes from a checkpoint after an interruption.
- Retries on rate limits and dropped connections, with backoff, and stops cleanly if progress stalls.
- Detects the Windows system proxy automatically, or takes an explicit proxy.
- Optional: videos, profile picture, dry-run listing.

## Requirements

- Python 3.9 or newer
- `instaloader` (installed from `requirements.txt`)
- Optional: `browser-cookie3` if you want to reuse a browser login

## Installation

```bash
git clone https://github.com/PayayaKamo/ins-downloader.git
cd ins-downloader

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Usage

```bash
# download a whole public profile into ./downloads
python ins_downloader.py namoridane

# profile URL instead of a username
python ins_downloader.py https://www.instagram.com/namoridane/

# custom output root, first 50 posts only, videos included
python ins_downloader.py namoridane -o D:/instagram -n 50 --videos

# limit by post date (UTC)
python ins_downloader.py namoridane --since 2024-01-01 --until 2025-12-31

# list what would be downloaded, without downloading anything
python ins_downloader.py namoridane --dry-run

# behind a proxy
python ins_downloader.py namoridane --proxy http://127.0.0.1:7890
```

Frequently used options:

| Option | Meaning |
| --- | --- |
| `-o, --output` | Output root directory (default: `downloads`) |
| `-n, --max-posts` | Maximum number of posts per profile, `0` means all |
| `--since` / `--until` | Only posts inside the given UTC date range |
| `--videos` | Also download videos (images only by default) |
| `--profile-pic` | Also download the profile picture |
| `--skip-pinned` | Skip pinned posts |
| `--login USER` | Log in as `USER` (private profiles or rate limits) |
| `--cookies-from-browser BROWSER` | Reuse cookies from `chrome`, `edge`, `firefox`, ... |
| `--proxy` / `--no-proxy` | Force a proxy, or force a direct connection |
| `--dry-run` | Print what would be downloaded |
| `--post-delay` | Seconds to wait between posts (default: `1`) |

Run `python ins_downloader.py --help` for the full list.

## Authentication and environment variables

Public profiles can be downloaded without signing in. A login helps when Instagram rate-limits
anonymous requests, and is required for private profiles you follow.

Three ways to authenticate, in order of precedence:

1. `--login USER` together with a password:
   - `--password`, or the `INS_PASSWORD` environment variable, or an interactive prompt.
   - The session is then cached, so later runs do not ask for the password again
     (`~/.instaloader/session-USER`, or the path given with `--session-file`).
2. `--cookies-from-browser chrome` (also `edge`, `firefox`, `brave`, ...) to reuse the login
   already present in your browser. Requires `pip install browser-cookie3`.
3. A local `.env` file next to the script.

Supported variables:

| Variable | Purpose |
| --- | --- |
| `INS_USERNAME` | Default value for `--login` |
| `INS_PASSWORD` | Password used by `--login` when `--password` is omitted |
| `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` | Proxy used for all requests |

Environment variables that are already set take precedence over values in `.env`.

Setup:

```bash
cp .env.example .env
# then edit .env and fill in your own values
```

> Credentials are never stored in the repository. `.env`, cookies and session files are all
> listed in `.gitignore`. Do not commit them, and do not paste real cookies into issues.

## Output

By default everything lands in `downloads/` relative to the current directory, in one
sub-directory per profile:

```text
downloads/
└── namoridane/
    ├── 2025-09-22_09-00-03_DO4jShFklJW.jpg       # first image of the post
    ├── 2025-09-22_09-00-03_DO4jShFklJW_1.jpg     # second frame of a carousel
    ├── 2025-09-22_09-00-03_DO4jShFklJW.txt       # caption
    ├── 2025-09-22_09-00-03_DO4jShFklJW.json      # full metadata
    ├── _index.csv                                # one row per post
    └── _resume_posts.json                        # checkpoint used when resuming
```

The target directory can be moved elsewhere with `-o`. File names follow
`{date_local:%Y-%m-%d_%H-%M-%S}_{shortcode}` and can be changed with `--filename-pattern`.

`_index.csv` columns: `shortcode`, `date_local`, `date_utc`, `type`, `media_count`, `likes`,
`comments`, `local_file`, `url`, `caption`.

## Resuming and exit codes

If a run is interrupted, for example by a network failure or Instagram throttling, just run the
same command again. Finished files are skipped and the checkpoint in `_resume_posts.json` tells
the tool where to continue.

| Exit code | Meaning |
| --- | --- |
| `0` | Everything was processed and every download succeeded |
| `1` | The profile does not exist, or a login is required but missing |
| `2` | Partial run: some posts failed or the iterator did not reach the end |
| `3` | No progress for `--stall-timeout` seconds, checkpoint saved |

## Connection check

`check_connection.py` makes a single read-only request and prints account statistics plus the
latest posts. It downloads nothing, so it is a quick way to test network, proxy or login setup.

```bash
python check_connection.py namoridane
python check_connection.py namoridane --proxy http://127.0.0.1:7890
```

## Responsible use

The tool only reads content that the profile owner has made public. Use it for personal
archiving or with the owner's permission, respect Instagram's terms of service and the
copyright of the original creator. Do not redistribute downloaded material without permission.
