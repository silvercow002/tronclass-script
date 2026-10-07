import argparse
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
import time

import yaml

from tron import Tronclass
from schemas import Config


def configure_logging(debug=False, log_dir=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.addFilter(lambda record: record.levelno < logging.WARNING)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    handlers = [stdout_handler, stderr_handler]
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(RotatingFileHandler(
            log_dir / 'tronclass.log', maxBytes=5 * 1024 * 1024,
            backupCount=3, encoding='utf-8',
        ))
    logging.basicConfig(
        format='[%(asctime)s.%(msecs)03d] %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        level=logging.DEBUG if debug else logging.INFO,
        handlers=handlers,
        force=True,
    )
    # HTTP debug output includes CAS tickets in redirect URLs.
    logging.getLogger('urllib3').setLevel(logging.WARNING)


def check_rollcalls(client, confirmed_ids):
    data = client.rollcall()
    confirmed_ids.intersection_update(item.rollcall_id for item in data.rollcalls)
    for item in data.rollcalls:
        rcid = item.rollcall_id
        if item.status == 'on_call_fine':
            if rcid not in confirmed_ids:
                logging.info('ID: %s attendance confirmed by server', rcid)
                confirmed_ids.add(rcid)
            continue
        confirmed_ids.discard(rcid)
        if item.is_expired:
            continue
        try:
            if item.is_number:
                logging.info('ID: %s starting Number rollcall', rcid)
                details = client.student_rollcall(rcid)
                client.answer_num(rcid, details.number_code)
            elif item.is_radar:
                logging.info('ID: %s starting Location rollcall', rcid)
                client.answer_radar(rcid)
            else:
                logging.debug('ID: %s unsupported rollcall type: %s', rcid, item.type)
                continue
            logging.info('ID: %s answer submitted; awaiting server confirmation', rcid)
        except Exception:
            logging.exception('ID: %s rollcall failed', rcid)


def run(config):
    client = Tronclass(config)
    client.login()
    working = False
    confirmed_ids = set()
    while True:
        now = datetime.now()
        schedule = config.operating[now.weekday()]
        if not schedule.enable:
            working = False
            logging.info('off working day; sleep...')
            time.sleep(3600)
            continue

        start, end = [datetime.strptime(t, '%H:%M').time() for t in schedule.range]
        if not start <= now.time() <= end:
            if working:
                logging.info('off working time')
            working = False
            logging.debug('sleep...')
            time.sleep(300)
            continue

        if not working:
            logging.info('starting working')
            working = True
        try:
            logging.debug('%s - checking', client.counter)
            check_rollcalls(client, confirmed_ids)
        except Exception:
            logging.exception('rollcall check failed')

        client.counter += 1
        time.sleep(config.config.Senkaku)


def main(argv=None):
    parser = argparse.ArgumentParser(description='TronClass attendance client')
    parser.add_argument('-c', '--config', type=Path, help='Path to config file')
    parser.add_argument('-l', '--log', type=Path, help='Directory for rotating log files')
    parser.add_argument('--debug', action='store_true', help='Enable detailed application logs')
    parser.add_argument(
        '--rollcall-id', help='Fetch one rollcall detail and exit without submitting an answer',
    )
    args = parser.parse_args(argv)
    config_path = args.config or Path(__file__).parent.parent / 'config.yaml'
    with config_path.open('r', encoding='utf-8') as file:
        config = Config.model_validate(yaml.safe_load(file))

    log_dir = args.log
    if log_dir is None and config.config.enable_log:
        log_dir = Path(__file__).parent.parent / 'log'
    configure_logging(args.debug, log_dir)
    logging.info('using config: %s; account: ***%s', config_path.resolve(), config.account.user[-3:])

    if args.rollcall_id:
        client = Tronclass(config)
        client.login()
        details = client.student_rollcall(args.rollcall_id)
        logging.info('rollcall ID: %s, code: %s', args.rollcall_id, details.number_code)
        return
    run(config)


if __name__ == '__main__':
    main()
