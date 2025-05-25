# Tronclass script

> Script for automating attendance in TronClass
---

## Requirements

- Python 3.8+

## Features
- Wait for rollcall to start and automatically answer
    - number
    <!-- - radar  -->
<!-- - Get notifications via Apprise -->

## Installation
1. Install required packages

```bash
pip install -r requirements.txt
```
2. Configure setting
- Fill in the information in the `config.yaml`

```yaml
...
account:
  user: '學號'
  passwd: '密碼'
...
```

3. Run it
```bash
python3 tron.py
```
---
## TODO
- radar
- notify(ex. telegram)
- upload sometime