import sys
import yaml
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
import logging

from tron import Tronclass
from schemas import *

sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(
    format='[%(asctime)s.%(msecs)03d] %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S', 
    level=logging.DEBUG
)


parser = argparse.ArgumentParser(description='i too lazy so here is not descroption')
parser.add_argument('-c', '--config', type=str, help="Path to config file")
parser.add_argument('-l', '--log', type=str, help="Path to save file location")
args = parser.parse_args()

LOGPATH = Path(args.log) if args.log else Path(__file__).parent.parent / 'log'
YAMLPATH = Path(args.config) if args.config else Path(__file__).parent.parent / 'config.yaml'

with open(YAMLPATH, 'r', encoding='utf-8') as file:
    CONFIG = yaml.safe_load(file)

def check_rollcell(data: Rollcall) -> tuple[int, str]:

    if data.rollcalls:
        inner_data = data.rollcalls[0]
        
        if inner_data.status == "on_call_fine":
            return 0, None
        elif inner_data.is_number:
            return 1, inner_data
        elif inner_data.is_radar:
            # TODO: radar
            pass
        else:
            print("maybe qrcode")
    else:
        return -1, None


def main():
    dummy = Tronclass(CONFIG['account'], CONFIG['config'])

    while True:
        dummy.login()
        dummy.student_rollcall('2145183') 
        time.sleep(1)
    return
    _night = False
    _workday = False
    while True:
        schedule = CONFIG['operating'][datetime.today().weekday()]
        start, end = [datetime.strptime(t, "%H:%M").time() for t in schedule['range']]
        current_time = datetime.now().time()

        if not schedule['enable']:
            time.sleep(3600)
        else:
            if start <= datetime.now().time() <= end:
                if not _night:
                    _night = True
            else:
                if _workday:
                    _workday = False
            
                time.sleep(300)
                continue

        try:
            check_rollcell(dummy.rollcall())
            if not _workday:
                _workday = True
            pass
        except Exception as e:
            pass



main()

    