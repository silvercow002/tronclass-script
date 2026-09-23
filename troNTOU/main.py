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
    level=logging.INFO
)


parser = argparse.ArgumentParser(description='i too lazy so here is not descroption')
parser.add_argument('-c', '--config', type=str, help="Path to config file")
parser.add_argument('-l', '--log', type=str, help="Path to save file location")
args = parser.parse_args()

LOGPATH = Path(args.log) if args.log else Path(__file__).parent.parent / 'log'
YAMLPATH = Path(args.config) if args.config else Path(__file__).parent.parent / 'config.yaml'

with open(YAMLPATH, 'r', encoding='utf-8') as file:
    CONFIG = yaml.safe_load(file)


def main():
    dummy = Tronclass(CONFIG['account'], CONFIG['config'])
    dummy.login()
    _night = False
    _workday = False
    while True:
        schedule = CONFIG['operating'][datetime.today().weekday()]
        start, end = [datetime.strptime(t, "%H:%M").time() for t in schedule['range']]

        if not schedule['enable']:
            logging.info('off working day')
            logging.info('sleep...')

            time.sleep(3600)
        else:
            if start <= datetime.now().time() <= end:
                if not _night:
                    _night = True
                    logging.info('starting working')
            else:
                if _workday:
                    _workday = False
                    logging.info('off working time')

                logging.info('sleep...')
                time.sleep(300)
                continue

        try:
            logging.info(f'{dummy.counter} - checking ')
            data = dummy.rollcall()
            if data.rollcalls:
                inner_data = data.rollcalls[0]
                if inner_data.status == "on_call_fine":
                    logging.info(f'ID: {inner_data.rollcall_id} is rollcalled')
                elif inner_data.is_number:
                    logging.info(f'ID: {inner_data.rollcall_id} starting Number rollcall')
                    dummy.student_rollcall()
                    dummy.answer_num()
                elif inner_data.is_radar:
                    logging.info(f'ID: {inner_data.rollcall_id} starting Location rollcall')
                    dummy.answer_radar()
                else:
                    logging.info(f'ID: {inner_data.rollcall_id} rollcal type is not souppert.')
                    logging.debug('you fuck up :)')
            if not _workday:
                _workday = True
            pass
        except Exception as e:
            logging.error(f'{e}')
            pass

        dummy.counter += 1
        time.sleep(2)

main()

    