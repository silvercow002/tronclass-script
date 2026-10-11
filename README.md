# Tronclass script

> Script for automating attendance in TronClass
---


## Features
- Wait for rollcall to start and automatically answer
    - number
    - radar
    
- use SNS to notifitons
    - telegram
    - discord


## Requirements
- Python 3.12

## Install

### download release
Go to [Releases](https://github.com/silvercow002/tronclass-script/releases), select the desired version, expand **Assets**, and download the package matching your operating system and architecture.

| Operating System | Download File |
| --- | --- |
| Windows x86_64 (Standard Intel / AMD 64-bit) | `troNTOU-windows-x86_64.zip` |
| macOS Apple Silicon (M-series chips) | `troNTOU-macos-arm64.tar.gz` |
| macOS Intel | `troNTOU-macos-x86_64.tar.gz` |
| Linux x86_64 | `troNTOU-linux-x86_64.tar.gz` |
| Fedora Linux 43 x86_64 | `troNTOU-fedoraLinux-43-x86_64.tar.gz` |

double click it!

### Run as Script 
1. clone
```bash
git clone https://github.com/silvercow002/tronclass-script
cd tronclass-script
```
2. set venv
```bash
python -m venv .venv
```

```bash
# windows
.\.venv\Scripts\Activate.ps1
# linux
source .venv/bin/activate
```
3. install dependencies

```bash
pip install -r requirements.txt
```
4. run it!

```bash
python ./troNTOU/main.py 
```




## config.ymal
### Acconut
Enter your TronClass username and password, keeping the quotation marks
```yaml
account:
  user: '學號'
  passwd: '密碼'
```
### Notifications
```
notifications:
  tg:
    enable: false
    key: ''   # Telegram bot token
    chat: ''  # Telegram chat ID
  dc:
    enable: false
    key: ''   # Discord bot token
    chat: ''  # Discord channel ID
```
### Schedule
In `operating`, `0` through `6` represent Monday through Sunday, respectively. Times are based on the local time zone of the host machine.
By default, the provided configuration is active daily from `09:00` to `17:00`. For example, to configure Monday only:
```yaml
operating:
  0:
    enable: true
    range: ['09:00', '17:00']

---
## TODO
- add more api endpoint...?