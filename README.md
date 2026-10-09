<p align="center">
  <h1 align="center">neoviu</h1>
</p>
<p align="center">
  <sup>
  A maintained fork of Viu: your browser anime experience, from the terminal.
  </sup>
</p>
<div align="center">

[![Fork of viu-media/viu](https://img.shields.io/badge/fork%20of-viu--media%2Fviu-blue?logo=github)](https://github.com/viu-media/viu)
[![Last commit](https://img.shields.io/github/last-commit/NehemiahAklil/neoviu)](https://github.com/NehemiahAklil/neoviu/commits/master)
[![License: Unlicense](https://img.shields.io/badge/license-Unlicense-blue)](LICENSE)

</div>

[viu-showcase.webm](https://github.com/user-attachments/assets/5da0ec87-7780-4310-9ca2-33fae7cadd5f)

<details>
<summary>Rofi</summary>
  
  [viu-showcase-rofi.webm](https://github.com/user-attachments/assets/01f197d9-5ac9-45e6-a00b-8e8cd5ab459c)

</details>

<details>
  <summary>RICED</summary>
  
  *main menu*
  
  <img width="1895" height="1007" alt="image" src="https://github.com/user-attachments/assets/e6d8883f-0267-4783-9688-983dea524e78" />
  
  *anime preview menu*
  
  <img width="1895" height="1007" alt="image" src="https://github.com/user-attachments/assets/3b887bcc-a601-4c04-b477-8328f50c227d" />

*episode menu*

  <img width="1895" height="1007" alt="image" src="https://github.com/user-attachments/assets/f6284c55-a1a9-4720-83a0-efca0a767c85" />

</details>

> [!IMPORTANT]
> This project scrapes public-facing websites for its streaming / downloading capabilities and primarily acts as an anilist, jikan and many other media apis tui client. The developer(s) of this application have no affiliation with these content providers. This application hosts zero content and is intended for educational and personal use only. Use at your own risk.
>
> [**Read the Full Disclaimer**](DISCLAIMER.md)

## About neoviu

neoviu continues [Viu](https://github.com/viu-media/viu), the terminal anime client created by [Benexl](https://github.com/Benexl) and its contributors. It keeps Viu's `viu` command, configuration file, and local data, so an existing Viu setup keeps working.

### Why This Fork Exists

We installed Viu, ran its tests, and tried to stream well-known titles such as Naruto, Death Note, and One Punch Man. The upstream project could no longer stream them:

- The [upstream repository](https://github.com/viu-media/viu) is archived and read-only. Its last release is v3.5.0 (May 6, 2026), and its last commit (May 9, 2026) deleted the AllAnime, AnimePahe, and AnimeUnity packages while the CLI still offered all three as providers.
- The provider registry also listed HiAnime, Nyaa, and Yugen, which had no implementation in the upstream code.
- AllAnime changed its API, and curd deprecated its own AllAnime provider instead of fixing it. AnimePahe now requires DDoS-Guard browser verification, which a terminal HTTP client can't pass.
- None of the upstream branches had provider fixes newer than the default branch.

The archived repository can't accept fixes, so we forked it as neoviu.

### How We Found Working Providers

We studied two actively maintained terminal anime clients to learn which sites still work and how they serve streams:

- [ani-cli](https://github.com/pystardust/ani-cli) scrapes HiAnime. Its current search, episode, and server flow, including the ZokoAnime and MegaPlay embeds, is the basis of neoviu's `hianime` provider.
- [curd](https://github.com/Wraient/curd) supports several catalogues. Its AniPub provider, which pairs the anipub.xyz catalogue with MegaPlay streams, is the basis of neoviu's `anipub` provider.

We also looked at [Seanime](https://github.com/5rahim/seanime), but it's a self-hosted media server rather than a streaming source, so it doesn't fit as a provider.

ani-cli and curd are GPL-3.0 projects, while neoviu stays in the public domain under the Unlicense. For that reason, neoviu reimplements the site protocols they document in Python and doesn't copy their code.

We then repaired AnimeUnity against its current site and removed every provider that no longer works, rather than leaving broken choices in the menus.

### What's Different From Viu

- **Working providers:** `hianime` (the default), `anipub`, and `animeunity`. See [Providers and Live-Site Restrictions](#providers-and-live-site-restrictions).
- **Config migration:** Saved configurations that select a removed provider or server switch to HiAnime and `TOP`, with a notice.
- **Any video height:** The quality setting accepts values such as `800`. When the preferred height is unavailable, neoviu plays the provider's top-ranked stream.
- **Reliable playback:** MPV receives each provider header separately, and neoviu reports MPV errors instead of ignoring them.
- **Clear provider errors:** Blocked or changed sites show an error and return to the previous menu instead of crashing the session.
- **Grid interface:** `viu tui` shows menus as tiles and anime as cover-art grids. See [The Grid Interface](#the-grid-interface-viu-tui).
- **AniList and MyAnimeList tracking:** As in curd, you choose where progress is synced: AniList, MyAnimeList, both, or neither. neoviu prompts you to log in and updates your list as you watch. See [Tracking Your Progress](#tracking-your-progress-viu-tracker).
- **Tests:** Offline regression tests cover every provider, and optional live tests check real streams.

## Core Features

- 📺 **Interactive TUI:** Browse, search, and manage your AniList library in a rich terminal interface powered by `fzf`, `rofi`, or a built-in selector.
- 🖼️ **Grid Interface:** Browse anime as a grid of cover images, open a details page, and change your status, progress, or score in a few keystrokes.
- 🔄 **List Sync:** Keep AniList, MyAnimeList, or both up to date automatically, and browse your lists by status (Watching, Planning, Completed, and more).
- ⚡ **Powerful Search:** Filter the entire AniList database with over 20 different criteria, including genres, tags, year, status, and score.
- 💾 **Local Registry:** Maintain a fast, local database of your anime for offline access, detailed stats, and robust data management.
- ⚙️ **Background Downloader:** Queue episodes for download and let a persistent background worker handle the rest.
- 📜 **Scriptable CLI:** Automate streaming and downloading with powerful, non-interactive commands perfect for scripting.
- 🔧 **Highly Customizable:** Tailor every aspect—from UI colors and providers to playback behavior—via a simple, well-documented configuration file.
- 🔌 **Extensible Architecture:** Easily add new providers, media players, and UI selectors to fit your workflow.

## Installation

neoviu runs on Windows, macOS, Linux, and Android (via Termux) with Python 3.11 or later. neoviu isn't published to PyPI, so install it directly from this repository. The package keeps the name `viu-media` and installs the same `viu` command.

> [!WARNING]
> The `viu-media` package on PyPI, the AUR packages, the upstream Nix flake, and the upstream release binaries install the archived Viu without neoviu's provider fixes. If you installed Viu one of those ways, uninstall it first, for example with `uv tool uninstall viu-media`.

### Prerequisites

For the best experience, please install these external tools:

- **Required for Streaming:**
  - [**mpv**](https://mpv.io/installation/) - The primary and recommended media player.
- **Recommended for UI & Previews:**
  - [**fzf**](https://github.com/junegunn/fzf) - For the best fuzzy-finder interface.
  - [**chafa**](https://github.com/hpjansson/chafa) or [**kitty's icat**](https://sw.kovidgoyal.net/kitty/kittens/icat/) - For image previews in the terminal.
- **Recommended for Downloads & Advanced Features:**
  - [**ffmpeg**](https://www.ffmpeg.org/) - Required for downloading HLS streams and merging subtitles.
  - [**webtorrent-cli**](https://github.com/webtorrent/webtorrent-cli) - For streaming torrents directly.

### Quick Install (recommended)

The install script sets up [**uv**](https://github.com/astral-sh/uv) (and a compatible Python, if needed), installs neoviu with all features including the grid interface, puts `viu` on your PATH, and tells you which external tools are missing.

**Linux, macOS, and Termux:**

```bash
curl -fsSL https://raw.githubusercontent.com/NehemiahAklil/neoviu/master/install.sh | bash
```

**Windows (PowerShell):**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/NehemiahAklil/neoviu/master/install.ps1 | iex"
```

Run the same command again to update to the latest version. Then open a new terminal and run `viu --help`.

The script accepts a few options (on Windows, download `install.ps1` and use `-Ref`, `-Extras`, `-Local`, `-Editable`):

```bash
# Install a specific branch, tag, or commit
curl -fsSL https://raw.githubusercontent.com/NehemiahAklil/neoviu/master/install.sh | bash -s -- --ref my-branch

# Choose the extras yourself (default: standard,tui)
curl -fsSL https://raw.githubusercontent.com/NehemiahAklil/neoviu/master/install.sh | bash -s -- --extras download,tui
```

> [!NOTE]
> On Linux, the `standard` extra builds `dbus-python` for desktop notifications, which needs system headers (`sudo apt install libdbus-1-dev pkg-config` on Debian/Ubuntu). If that build fails, the script retries without notification support, so the install still completes.

### Install from a Clone (for testing changes)

Running the script from inside a checkout installs that checkout, including uncommitted changes, instead of the GitHub version:

```bash
git clone https://github.com/NehemiahAklil/neoviu.git
cd neoviu
./install.sh             # installs this checkout as the `viu` command
./install.sh --editable  # same, but code edits take effect without reinstalling
```

You can also run neoviu without installing it: `uv run viu --help`.

### Manual Install (uv)

If you'd rather run the commands yourself:

```bash
# Install with all optional features for the full experience
uv tool install "viu-media[standard,tui] @ git+https://github.com/NehemiahAklil/neoviu.git"

# Or, pick and choose the extras you need:
uv tool install "viu-media @ git+https://github.com/NehemiahAklil/neoviu.git"  # Core functionality only
uv tool install "viu-media[download] @ git+https://github.com/NehemiahAklil/neoviu.git"  # For advanced downloading with yt-dlp
uv tool install "viu-media[discord] @ git+https://github.com/NehemiahAklil/neoviu.git"   # For Discord Rich Presence
uv tool install "viu-media[notifications] @ git+https://github.com/NehemiahAklil/neoviu.git" # For desktop notifications
uv tool install "viu-media[tui] @ git+https://github.com/NehemiahAklil/neoviu.git"       # For the grid interface (viu tui)
```

To update neoviu to the latest commit, run the same install command with `--reinstall`:

```bash
uv tool install --reinstall "viu-media[standard,tui] @ git+https://github.com/NehemiahAklil/neoviu.git"
```

To uninstall: `uv tool uninstall viu-media`.

### Pre-built Binaries

neoviu doesn't publish pre-built binaries yet. The binaries on the [upstream releases page](https://github.com/viu-media/viu/releases/latest) are builds of the archived Viu and don't include neoviu's provider fixes.

### Other Installation Methods

<details>
  <summary><b>Platform-Specific and Alternative Installers</b></summary>
  
> [!NOTE]
> The Nix and AUR commands below install the archived upstream Viu, not neoviu. Use the Termux, pipx, or pip instructions to install neoviu.

#### Nix / NixOS

##### Ephemeral / One-Off Run (No Installation)

  ```bash
  nix run github:viu-media/viu
  ```

##### Imperative Installation

  ```bash
  nix profile install github:viu-media/viu
  ```

##### Declarative Installation

###### in your flake.nix

  ```nix
  viu.url = "github:viu-media/viu";
  ```

###### in your system or home-manager packages

  ```nix
  inputs.viu.packages.${pkgs.system}.default
  ```

#### Arch Linux (AUR)

Use an AUR helper like `yay` or `paru`.

```bash
# Stable version (recommended)
yay -S viu-media

# Git version (latest commit)
yay -S viu-media-git
```

#### Termux

You may have to have rust installed see this issue: <https://github.com/pydantic/pydantic-core/issues/1012#issuecomment-2511269688>.

```bash
# Recommended (with pip due to more control)
pkg install python
pkg install rust # required cause of pydantic

# NOTE: order matters

# get pydantic from the termux user repository
pip install pydantic --extra-index-url https://termux-user-repository.github.io/pypi/

# the above will take a while if you want to see more output and feel like sth is happening lol
pip install pydantic --extra-index-url https://termux-user-repository.github.io/pypi/ -v

# now you can install neoviu (git is required to install from the repository)
pkg install git
pip install "viu-media @ git+https://github.com/NehemiahAklil/neoviu.git"

# === optional deps ===
# if you have reach here awesome lol :)

# yt-dlp for downloading m3u8 and hls streams
pip install yt-dlp[default,curl-cffi]

# you may also need ffmpeg for processing the videos
pkg install ffmpeg

# tip if you also want yt functionality
pip install yt-dlp-ejs

# you require js runtime
# eg the recommended one
pkg install deno

# for faster fuzzy search
pip install thefuzz

# if you want faster scraping, though barely noticeable lol
pip install lxml --extra-index-url https://termux-user-repository.github.io/pypi/

# if compilation fails you need to have
pkg install libxml2 libxslt

# == ui setup ==
pkg install fzf

# then enable fzf in the config
viu --selector fzf config --update

# if you want previews as well specify preview option
# though images arent that pretty lol, so you can stick to text over full
viu --preview text config --update

# if you set preview to full you need a terminal image renderer
pkg install chafa

# == player setup ==
# for this you need to strictly install from playstore
# search for mpv or vlc (recommended, since has nicer ui)
# the only limitation is currently its not possible to pass headers to the android players
# through android intents
# hianime and anipub streams need a Referer header, so use animeunity
# (italian-language) for streaming on android
# though this is not an issue when it comes to downloading ;)
# if you have installed using 'pkg' uninstall it

# okey now you are all set, i promise the hussle is worth it lol :)
# posted a video of it working to motivate you
# note i recorded it from waydroid which is android for linux sought of like an emulator(bluestacks for example)
```

<https://github.com/user-attachments/assets/0c628421-a439-4dea-91bb-7153e8f20ccf>

#### Using pipx (for isolated environments)

```bash
pipx install "viu-media[standard] @ git+https://github.com/NehemiahAklil/neoviu.git"
```

#### Using pip

```bash
pip install "viu-media[standard] @ git+https://github.com/NehemiahAklil/neoviu.git"
```

</details>

<details>
  <summary><b>Building from Source</b></summary>
  
  Requires [Git](https://git-scm.com/), [Python 3.11+](https://www.python.org/), and [uv](https://astral.sh/blog/uv).

  ```bash
  git clone https://github.com/NehemiahAklil/neoviu.git --depth 1
  cd neoviu
  ./install.sh   # or: uv tool install ".[standard,tui]"
  viu --version
  ```

</details>

> [!TIP]
> Enable shell completions for a much better experience by running `viu completions` and following the on-screen instructions for your shell.

## Getting Started: Quick Start

Get up and running in three simple steps:

1. **Connect your anime list:**

    ```bash
    viu tracker login
    ```

    neoviu asks whether to sync with AniList, MyAnimeList, both, or neither, then opens your browser to log in. You can skip this step, because neoviu also offers to log you in the first time it needs your list. `viu anilist auth` still works for AniList.

2. **Launch the interface:**

    ```bash
    viu anilist   # the classic fzf/rofi menus
    viu tui       # the grid interface (requires the tui extra)
    ```

3. **Browse & Play:** Use your arrow keys to navigate, select an anime, and choose an episode to stream instantly. Your progress is saved locally and synced to the sites you connected.

## Usage Guide

### The Interactive TUI (`viu anilist`)

This is the main, user-friendly way to use neoviu. It provides a rich terminal experience where you can:

- Browse trending, popular, and seasonal anime.
- Manage your personal lists (Watching, Completed, Paused, etc.).
- Search for any anime in the AniList database.
- View detailed information, characters, recommendations, reviews, and airing schedules.
- Stream or download episodes directly from the menus.

### The Grid Interface (`viu tui`)

The grid interface is a full-screen alternative to the selector menus, built with [Textual](https://github.com/Textualize/textual). It requires the `tui` extra. Start it with `viu tui`, or set `interface = "grid"` in the `[general]` config section to make `viu` and `viu anilist` open it by default.

- **Home:** Tiles for Continue Watching, My Library, Search, Trending, Popular, Top Scored, Recently Updated, Upcoming, Most Favourited, Recently Watched, Random, Trackers, and the Classic Menu.
- **Grids:** Anime appear as cards with cover art, format, episode count, score, and your list status.
- **My Library:** One tab per list status: Watching, Planning, Completed, Paused, Dropped, and Rewatching. The lists come from the tracker you are logged in to.
- **Details:** The details page shows the synopsis, airing schedule, and your entry on each tracker. You can play, pick an episode, or change the status, progress, and score from there.

Playback hands off to the same provider and player flow as the classic menus, then returns you to the grid.

Cover images render with [textual-image](https://github.com/lnqs/textual-image), which picks the best protocol your terminal supports: Kitty graphics, Sixel, or Unicode blocks. Pass `--no-images` to turn covers off, for example over a slow SSH connection.

| Key | Where | Action |
| --- | --- | --- |
| Arrow keys, `Home`, `End` | Grids | Move between cards |
| `Enter` | Grids | Open the selected card |
| `n` / `p` / `r` | Grids | Next page, previous page, refresh |
| `/` | Home, Search | Search |
| `l` / `c` / `t` | Home | Library, Continue Watching, Trackers |
| `[` / `]` or `1`–`6` | Library | Switch list tabs |
| `p` / `e` | Details | Play or continue, choose an episode |
| `s` / `+` / `-` / `c` | Details | Set status, progress +1, progress −1, set score |
| `x` / `o` | Details | Remove from list, open the AniList page |
| `Esc` | Anywhere | Go back |
| `q` | Home | Quit |

### Tracking Your Progress (`viu tracker`)

neoviu always keeps your watch history locally. The `tracking.remote` setting decides which sites also receive status, progress, and score changes: `anilist` (the default), `myanimelist`, `both`, or `none`.

```bash
viu tracker                     # show which trackers are enabled and logged in
viu tracker mode both           # sync to AniList and MyAnimeList
viu tracker login               # log in to every enabled tracker
viu tracker login myanimelist   # log in to one site
viu tracker logout              # log out of both sites
```

Tracking works the same way in the classic menus and the grid interface:

- Finishing an episode moves your progress forward.
- An anime that isn't on your list yet is added as **Watching**.
- Watching the last episode marks the anime **Completed**.
- When a tracker you enabled isn't logged in, neoviu offers to log you in once per session. Set `tracking.prompt_login = false` to turn this prompt off.

With both sites enabled, your lists come from AniList, and every change goes to both.

#### Setting Up MyAnimeList

MyAnimeList requires each user to register their own API client, so neoviu can't ship one. The setup is a one-time step:

1. Open [myanimelist.net/apiconfig](https://myanimelist.net/apiconfig) and select **Create ID**.
2. Set **App Type** to `other` and **App Redirect URL** to `http://localhost:8123/callback`. Fill in the remaining fields however you like.
3. Run `viu tracker login myanimelist` and paste the client ID when neoviu asks for it. You can also set `tracking.mal_client_id` in the config file or the `VIU_MAL_CLIENT_ID` environment variable.

neoviu then opens your browser and catches the login redirect on port 8123 automatically. If that port is busy, change `tracking.mal_redirect_port` and update the redirect URL on MyAnimeList to match. If the redirect page doesn't load, copy its full URL from the address bar and paste it into the terminal.

### Powerful Searching (`viu anilist search`)

Filter the entire AniList database with powerful command-line flags.

```bash
# Search for anime from 2024, sorted by popularity, that is releasing and not on your list
viu anilist search -y 2024 -s POPULARITY_DESC --status RELEASING --not-on-list

# Find the most popular movies with the "Fantasy" genre
viu anilist search -g Fantasy -f MOVIE -s POPULARITY_DESC

# Dump search results as JSON instead of launching the TUI
viu anilist search -t "Demon Slayer" --dump-json
```

### Background Downloads (`viu queue` & `worker`)

neoviu includes a robust background downloading system.

1. **Add episodes to the queue:**

    ```bash
    # Add episodes 1-12 of Jujutsu Kaisen to the download queue
    viu queue add -t "Jujutsu Kaisen" -r "0:12"
    ```

2. **Start the worker process:**

    ````bash
    # Run the worker in the foreground (press Ctrl+C to stop)
    viu worker

    # Or run it as a background process
    viu worker &
    ```The worker will now process the queue, download your episodes, and check for notifications.
    ````

### Scriptable Commands (`download` & `search`)

These commands are designed for automation and quick, non-interactive tasks.

#### `download` Examples

```bash
# Download the latest 5 episodes of One Piece
viu download -t "One Piece" -r "-5"

# Download episodes 1 to 24, merge subtitles, and clean up original files
viu download -t "Jujutsu Kaisen" -r "0:24" --merge --clean
```

#### `search` (Binging) Examples

```bash
# Start binging an anime from the first episode
viu search -t "Attack on Titan" -r ":"

# Watch the latest episode directly
viu search -t "My Hero Academia" -r "-1"
```

### Providers and Live-Site Restrictions

HiAnime is the default provider. Use `--provider` to choose another supported source; external websites can still become unavailable or restrict requests.

| Provider | Support |
| --- | --- |
| `hianime` | Uses ZokoAnime, with MegaPlay as a fallback. Supports sub/dub server selection, subtitles, and HLS resolutions such as 800p. |
| `anipub` | Uses AniPub's catalogue and MegaPlay streams. Supports sub/dub selection, subtitles, and both current and legacy episode links. |
| `animeunity` | Supports search, episode listings, and MP4 streams from the Italian-language service. |

AllAnime, AnimePahe, Nyaa, and Yugen have been removed rather than kept as non-working choices. When loading an older configuration, neoviu replaces a removed provider with HiAnime and retired server preferences with `TOP`, and displays a migration notice. It leaves the file unchanged until you run `viu config --update`; explicit command-line selections of removed providers are rejected.

The HiAnime implementation independently follows the current protocols documented by [ani-cli](https://github.com/pystardust/ani-cli). AniPub follows the catalogue and MegaPlay protocols used by [curd's AniPub provider](https://github.com/Wraient/curd/tree/main/internal/providers/anipub), sharing the existing MegaPlay extractor with HiAnime. Neither requires additional runtime dependencies.

Choose a provider explicitly when another site is unavailable. Episode ranges use zero-based indices, so `0:1` selects only the first episode:

```bash
viu --provider hianime search -t "Naruto" -r "0:1"

# Select the alternative HiAnime host explicitly.
viu --provider hianime --server megaplay search -t "Naruto" -r "0:1"

# Use the additional AniPub catalogue, including dubbed episodes.
viu --provider anipub --translation-type dub search -t "Death Note" -r "0:1"
```

Quality preferences accept positive numeric values, including nonstandard upstream resolutions such as `--quality 800`. If the preferred quality is unavailable, neoviu selects the provider's top-ranked stream without changing your saved preference.

Provider regression tests use synthetic responses and do not require network access:

```bash
uv run pytest tests/libs/provider tests/libs/player/mpv tests/cli/interactive tests/cli/commands/test_cli_stream_quality.py
```

The optional live tests check Naruto, Death Note, and One Punch Man across all supported providers. They verify search results, episode details, stream extraction, and a small MP4 or HLS prefix without launching a player or downloading an episode:

```bash
VIU_LIVE_TESTS=1 uv run pytest -m integration tests/libs/provider/anime/test_live.py
```

Live tests fail when a site blocks requests or returns unusable streams. The default test run skips these checks, so offline test success must not be interpreted as proof that an upstream site is available.

### Local Data Management (`viu registry`)

neoviu maintains a local database of your anime for offline access and enhanced performance.

- `registry sync`: Synchronize your local data with your remote AniList account.
- `registry stats`: Show detailed statistics about your viewing habits.
- `registry backup`: Create a compressed backup of your entire registry.
- `registry restore`: Restore your data from a backup file.
- `registry export/import`: Export/import your data to JSON/CSV for use in other applications.
- `registry clean`: Clean up orphaned or invalid entries from your local database.

## Configuration

neoviu is highly customizable. A default configuration file with detailed comments is created on the first run.

- **Find your config file:** `viu config --path`
- **Edit in your default editor:** `viu config`
- **Use the interactive wizard:** `viu config --interactive`

Most settings in the config file can be temporarily overridden with command-line flags (e.g., `viu --provider animeunity anilist`).

<details>
  <summary><b>Default Configuration (`config.ini`) Explained</b></summary>

```ini
# [general] Section: Controls overall application behavior.
[general]
provider = hianime           ; Anime provider: hianime, anipub, animeunity.
selector = fzf               ; The interactive UI tool (fzf, rofi, default).
preview = full               ; Preview type in selectors (full, text, image, none).
image_renderer = icat        ; Tool for terminal image previews (icat, chafa).
icons = True                 ; Display emoji icons in the UI.
interface = classic          ; What 'viu anilist' opens: classic menus or the grid.
auto_select_anime_result = True ; Automatically select the best search match.
...

# [tracking] Section: Controls syncing with AniList and MyAnimeList.
[tracking]
remote = anilist             ; Where progress is synced: anilist, myanimelist, both, none.
prompt_login = True          ; Offer to log in when an enabled tracker is logged out.
mal_client_id =              ; Your MyAnimeList API client ID.
mal_redirect_port = 8123     ; Local port that receives the MyAnimeList login redirect.

# [stream] Section: Controls playback and streaming.
[stream]
player = mpv                 ; The media player to use (mpv, vlc).
quality = 1080               ; Preferred numeric stream quality (e.g. 1080, 800, 720, 480, 360).
translation_type = sub       ; Preferred audio/subtitle type (sub, dub).
auto_next = False            ; Automatically play the next episode.
continue_from_watch_history = True ; Resume playback from where you left off.
use_ipc = True               ; Enable in-player controls via MPV's IPC.
...

# [downloads] Section: Controls the downloader.
[downloads]
downloader = auto            ; Downloader to use (auto, default, yt-dlp).
downloads_dir = ...          ; Directory to save downloaded anime.
max_concurrent_downloads = 3 ; Number of parallel downloads in the worker.
merge_subtitles = True       ; Automatically merge subtitles into the video file.
cleanup_after_merge = True   ; Delete original files after merging.
...

# [worker] Section: Controls the background worker process.
[worker]
enabled = True
notification_check_interval = 15 ; How often to check for new episodes (minutes).
download_check_interval = 5      ; How often to process the download queue (minutes).
...
```

</details>

## Advanced Features

### MPV IPC Integration

When `use_ipc = True` is set in your config, neoviu provides powerful in-player controls without needing to close MPV.

**Key Bindings:**

- `Shift+N`: Play the next episode.
- `Shift+P`: Play the previous episode.
- `Shift+R`: Reload the current episode.
- `Shift+A`: Toggle auto-play for the next episode.
- `Shift+T`: Toggle between `dub` and `sub`.

**Script Messages (For MPV Console):**

- `script-message select-episode <number>`: Jump to a specific episode.
- `script-message select-server <name>`: Switch to a different streaming server.

### Running as a Service (Linux/systemd)

You can run the background worker as a systemd service for persistence.

1. Create a service file at `~/.config/systemd/user/viu-worker.service`:

    ```ini
    [Unit]
    Description=neoviu Background Worker
    After=network-online.target

    [Service]
    Type=simple
    ExecStart=/path/to/your/viu worker --log
    Restart=always
    RestartSec=30

    [Install]
    WantedBy=default.target
    ```

    *Replace `/path/to/your/viu` with the output of `which viu`.*

2. Enable and start the service:

    ```bash
    systemctl --user daemon-reload
    systemctl --user enable --now viu-worker.service
    ```

## Projects Using Viu

**[Inazuma](https://github.com/viu-media/Inazuma)** - official gui wrapper over viu built in kivymd

## Contributing

Contributions are welcome! Whether it's reporting a bug, proposing a feature, or writing code, your help is appreciated. Please read our [**Contributing Guidelines**](CONTRIBUTIONS.md) to get started.

## Credits

neoviu builds on the work of these projects:

- **[Viu](https://github.com/viu-media/viu)** by [Benexl](https://github.com/Benexl) and its contributors is the foundation of neoviu. The interactive TUI, AniList integration, local registry, downloader, and nearly everything outside the providers come from Viu, which is released under the Unlicense.
- **[ani-cli](https://github.com/pystardust/ani-cli)** by [pystardust](https://github.com/pystardust) and its contributors documents the current HiAnime, ZokoAnime, and MegaPlay flow that the `hianime` provider follows.
- **[curd](https://github.com/Wraient/curd)** by [Wraient](https://github.com/Wraient) and its contributors documents the AniPub catalogue and MegaPlay stream decryption that the `anipub` provider follows. curd's tracker model, which offers AniList, MyAnimeList, both, or local only with a login prompt on first run, inspired `viu tracker`.
- **[Textual](https://github.com/Textualize/textual)** and **[textual-image](https://github.com/lnqs/textual-image)** power the grid interface.

ani-cli and curd are licensed under GPL-3.0. neoviu reimplements the site protocols they document and doesn't include their code. Thank you to everyone who builds and maintains these projects.
