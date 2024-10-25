# Full computer control with a simple CLI script

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**Surrender.py** lets Claude(*Computer Use*) take control of your machine through a tool-based interface.

https://github.com/user-attachments/assets/010f0d51-b9ca-4539-9b92-d5849efa870b

There are no safety features. Run at your own risks. You need an [Anthropic API key](https://www.anthropic.com/api) and around 0.15€ to reproduce the video above.

## Features

- 🏳️ No safety features (CTRL-C should work)
- Screenshot-Click debugging: logs where Claude clicked
- 🖥️ Full computer control (mouse, keyboard, screenshots)
- 🔧 Bash command execution & 📝 File editing capabilities

## Installation

```bash
git clone https://github.com/vmerckle/Aifor-Loop.git
cd Aifor-Loop ; pip install -r requirements.txt
```

Only if your API key is not exported:

```bash
echo ANTHROPIC_API_KEY = "your api key here" > .env
```

## Usage

```bash
python surrender.py "Apply for some machine learning jobs, but please don't delete my home folder by accident"
```


## Requirements

- Python 3.10+
- Anthropic API key
- Linux with X11 (for computer control features)
- Required system packages:
  - `xdotool`
  - `scrot` or `gnome-screenshot`
  - `imagemagick`

Install system requirements on Fedora:

```bash
sudo dnf install xdotool scrot imagemagick
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| ANTHROPIC_API_KEY | Your Anthropic API key | Yes |
| WIDTH | Screen width in pixels | No |
| HEIGHT | Screen height in pixels | No |
| DISPLAY_NUM | X11 display number | No |

## Architecture

Aifor-Loop uses a tool-based architecture where Claude can only interact with your computer through well-defined tool interfaces:

- `ComputerTool`: Screen, keyboard, and mouse control
- `BashTool`: Command execution
- `EditTool`: File operations

## Acknowledgments

- [Anthropic quickstart](https://github.com/anthropics/anthropic-quickstarts/tree/main)
