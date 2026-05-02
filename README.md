<div dir="ltr" align="left">

‎[čeština](/docs/cs/PŘEČTĚTEMĚ.md) | ‎**English** | ‎[español](/docs/es/LÉAME.md) | ‎[français](/docs/fr/LISEZMOI.md) | ‎[magyar](/docs/hu/OLVASSAEL.md) | ‎[Melayu](/docs/ms/BACASAYA.md) | ‎[português](/docs/pt/LEIAME.md) | ‎[русский](/docs/ru/ПРОЧТИМЕНЯ.md) | ‎[简体中文](/docs/zh-Hans/自述文件.md) | ‎[[+]](https://weblate.librescore.org/projects/librescore/docs)

[//]: # "\+\_==!|!=_=!|!==_/+/ ***DO NOT EDIT ABOVE THIS LINE*** /+/^^+#|#+^+#|#+^^\+\"

# dl-librescore

<div align="center">

<img src="https://github.com/LibreScore/dl-musescore/raw/master/images/logo.png" width="256" alt="LibreScore logo">

[![Discord](https://img.shields.io/discord/774491656643674122?color=5865F2&label=&labelColor=555555&logo=discord&logoColor=FFFFFF)](https://discord.gg/DKu7cUZ4XQ) [![Weblate](https://weblate.librescore.org/widgets/librescore/-/dl-librescore/svg-badge.svg)](https://weblate.librescore.org/engage/librescore) [![Github All Releases](https://img.shields.io/github/downloads/LibreScore/app-librescore/total.svg?label=App)](https://github.com/LibreScore/app-librescore/releases/latest) [![Github All Releases](https://img.shields.io/github/downloads/LibreScore/dl-librescore/total.svg?label=Userscript)](https://github.com/LibreScore/dl-librescore/releases/latest) [![npm](https://img.shields.io/npm/dt/dl-librescore?label=Command-line+tool)](https://www.npmjs.com/package/dl-librescore)

Download sheet music

</div>

> DISCLAIMER: This is not an officially endorsed MuseScore product

## Installation

There are 4 different installable programs:

| Program                                                                            | MSCZ | MIDI | MP3 | PDF | Conversion |     | Windows | macOS | Linux | Android | iOS/iPadOS |
| ---------------------------------------------------------------------------------- | ---- | ---- | --- | --- | ---------- | --- | ------- | ----- | ----- | ------- | ---------- |
| [App](#app)                             | ✔️   | ✔️   | ✔️  | ❌  | ❌         |     | ✔️      | ✔️    | ✔️    | ✔️      | ❌         |
| [Userscript](#userscript)               | ❌   | ✔️   | ✔️  | ✔️  | ❌         |     | ✔️      | ✔️    | ✔️    | ✔️      | ✔️         |
| [Command-line tool](#command-line-tool) | ❌   | ✔️   | ✔️  | ✔️  | ✔️         |     | ✔️      | ✔️    | ✔️    | ✔️      | ❌         |
| [Webmscore website](#webmscore-website) | ❌   | ❌   | ❌  | ❌  | ✔️         |     | ✔️      | ✔️    | ✔️    | ✔️      | ✔️         |

> Note: `Conversion` refers to the ability to convert files into other file types, including those not downloadable in the program.
> Conversion types include: Individual Parts, PDF, PNG, SVG, MP3, WAV, FLAC, OGG, MIDI, MusicXML, MSCZ, and MSCX.

### App

1. Go to the [README](https://github.com/LibreScore/app-librescore#installation) page of the `app-librescore` repository
2. Follow the installation instructions for your device

### Userscript

> Note: If your device is on iOS or iPadOS, please follow the [Shortcut](#shortcut) instructions.
>
> Note: If you cannot install browser extensions on your device, please follow the [Bookmark](#bookmark) instructions instead.

#### Browser extension

1. Install [Tampermonkey](https://www.tampermonkey.net)

> Note: If you already installed an old version of the script called "musescore-downloader", "mcsz downloader", or "musescore-dl", please uninstall it from the Tampermonkey dashboard

2. Go to the latest [dl-librescore.user.js](https://github.com/LibreScore/dl-librescore/releases/latest/download/dl-librescore.user.js) file
3. Press the Install button

#### Shortcut

1. Install the [LibreScore shortcut](https://www.icloud.com/shortcuts/901d8778d2da4f7db9272d3b2232d0fe)
2. In Safari, when viewing a song on MuseScore, tap <img src="https://help.apple.com/assets/61800C7E6EA4632586448084/61800C896EA463258644809A/en_US/01f5a9889bbecc202d8cbb3067a261ad.png" height="16">
3. Tap the LibreScore shortcut to activate the extension

> Note: Before you can run JavaScript from a shortcut you must turn on Allow Running Scripts
>
> 1. Go to Settings <img src="https://help.apple.com/assets/61800C7E6EA4632586448084/61800C896EA463258644809A/en_US/492fec5aff74dbdef9b526177c3804b4.png" height="16"> > Shortcuts > Advanced
> 2. Turn on Allow Running Scripts

#### Bookmark

1. Create a new bookmark (usually Ctrl+D)
2. Type `LibreScore` for the Name field
3. Type `javascript:(function () {let code = document.createElement('script');code.src = 'https://github.com/LibreScore/dl-librescore/releases/latest/download/dl-librescore.user.js';document.body.appendChild(code);}())` for the URL field
4. Save the bookmark
5. When viewing a song on MuseScore, click the bookmark to activate the extension

### Command-line tool

#### Quick start (npx)

1. Install [Node.js LTS](https://nodejs.org)
2. Open a terminal (do _not_ open the Node.js application)
3. Type `npx dl-librescore@latest`, then press `Enter ↵`

#### Local build (development)

1. Install [Node.js LTS](https://nodejs.org)
2. Clone this repository and `cd` into it
3. Run `npm install` to install dependencies
4. Run `npm run build` to compile

**Non-interactive** (provide URL and output type directly):
```
node ./dist/cli.js -i https://musescore.com/user/123/scores/456 -t pdf
```
Files are saved to `./downloaded_files/` by default. Override with `-o <dir>`.

**Interactive mode** (prompts for URL, format, and output directory):
```
node ./dist/cli.js
```

**All options:**

| Flag | Short | Description |
|------|-------|-------------|
| `--input` | `-i` | MuseScore URL or path to local file/folder |
| `--type` | `-t` | Output format(s): `pdf`, `mp3`, `midi`, `mscz`, `mscx`, `musicxml`, `flac`, `ogg` |
| `--output` | `-o` | Output directory (default: `./downloaded_files`) |
| `--verbose` | `-v` | Print each saved file path |

#### PDF quality and the browser fallback

When MuseScore's direct API is accessible the tool downloads PDFs at **~259 DPI** (raster). When blocked, it automatically falls back to a browser-based approach that produces a **true vector PDF** (infinite zoom, no pixelation) by:

1. Opening the score in a headless Chromium browser via [SeleniumBase](https://seleniumbase.io)
2. Downloading the score's SVG source files directly from MuseScore's CDN
3. Converting SVG → vector PDF with [cairosvg](https://cairosvg.org) + [pypdf](https://pypdf.readthedocs.io)

The fallback runs **automatically** — no extra steps needed. Prerequisites (installed once by [uv](https://docs.astral.sh/uv)):

- [uv](https://docs.astral.sh/uv/getting-started/installation/) — Python package manager
- System library `libcairo` — for cairosvg SVG rendering
  - Ubuntu/Debian: `sudo apt install libcairo2`
  - macOS: `brew install cairo`

If `libcairo` is not installed, the fallback produces 72 DPI screenshots instead of vector output.

### Webmscore website

1. Open [Webmscore](https://webmscore-pwa.librescore.org)

> Note: You can access the website offline by installing it as a PWA

## Building

1. Install [Node.js LTS](https://nodejs.org)
2. `npm install` to install packages
3. `npm run build` to build

- Install `./dist/main.user.js` with Tampermonkey
- `node ./dist/cli.js` to run command-line tool

</div>
