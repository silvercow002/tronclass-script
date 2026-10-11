import argparse
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
import time
import requests
import yaml

from tron import Tronclass
from schemas import Config


class Notifier:
    REQUEST_TIMEOUT = (5, 10)

    def __init__(self, config):
        self.config = config

    def send(self, text):
        text = f'{self.config.account.user}\n{text}'
        for name in ('tg', 'dc'):
            channel = getattr(self.config.notifications, name)
            if not channel.enable:
                continue
            if not channel.key.strip() or not channel.chat.strip():
                logging.warning('%s notification skipped: key and chat are required', name)
                continue
            if name == 'tg':
                token = channel.key.strip().removeprefix('bot')
                url = f'https://api.telegram.org/bot{token}/sendMessage'
                kwargs = {'json': {'chat_id': channel.chat.strip(), 'text': text[:4096]}}
            elif name == 'dc':
                url = f'https://discord.com/api/v10/channels/{channel.chat.strip()}/messages'
                kwargs = {
                    'headers': {'Authorization': f'Bot {channel.key.strip()}'},
                    'json': {'content': text[:2000], 'allowed_mentions': {'parse': []}},
                }
            try:
                with requests.post(url, timeout=self.REQUEST_TIMEOUT, **kwargs) as response:
                    response.raise_for_status()
                    if name == 'tg' and response.json().get('ok') is not True:
                        logging.warning('tg notification rejected by API')
            except (requests.RequestException, ValueError) as error:
                # Request exceptions may include the bot token in their URL.
                logging.warning('%s notification failed (%s)', name, type(error).__name__)


class DailyLogHandler(RotatingFileHandler):
    """Store daily logs under year/month directories, including across midnight."""

    def __init__(self, log_dir):
        self.log_dir = Path(log_dir).resolve()
        super().__init__(
            self.log_dir / 'tronclass.log', maxBytes=5 * 1024 * 1024,
            backupCount=3, encoding='utf-8', delay=True,
        )

    def emit(self, record):
        try:
            date = datetime.fromtimestamp(record.created)
            path = self.log_dir / str(date.year) / str(date.month) / f'{date.day}.log'
            if str(path) != self.baseFilename:
                path.parent.mkdir(parents=True, exist_ok=True)
                if self.stream is not None:
                    self.stream.close()
                    self.stream = None
                self.baseFilename = str(path)
            super().emit(record)
        except Exception:
            self.handleError(record)


def configure_logging(debug=False, log_dir=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.addFilter(lambda record: record.levelno < logging.WARNING)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    handlers = [stdout_handler, stderr_handler]
    if log_dir is not None:
        handlers.append(DailyLogHandler(log_dir))
    logging.basicConfig(
        format='[%(asctime)s.%(msecs)03d] %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        level=logging.DEBUG if debug else logging.INFO,
        handlers=handlers,
        force=True,
    )
    # HTTP debug output includes CAS tickets in redirect URLs.
    logging.getLogger('urllib3').setLevel(logging.WARNING)


def check_rollcalls(client, notified_events, notifier):
    data = client.rollcall()
    active_ids = {item.rollcall_id for item in data.rollcalls}
    for rcid in notified_events.keys() - active_ids:
        del notified_events[rcid]
    for item in data.rollcalls:
        rcid = item.rollcall_id
        events = notified_events.setdefault(rcid, set())
        context = f'ID: {rcid}\nCourse: {item.course_title}'
        if item.status == 'on_call_fine':
            if 'confirmed' not in events:
                logging.info('ID: %s attendance confirmed by server', rcid)
                notifier.send(f'Attendance confirmed by server\n{context}')
                events.add('confirmed')
            continue
        if item.is_expired:
            continue
        if not (item.is_number or item.is_radar):
            logging.debug('ID: %s unsupported rollcall type: %s', rcid, item.type)
            continue
        try:
            kind = 'Number' if item.is_number else 'Location'
            logging.info('ID: %s starting %s rollcall', rcid, kind)
            if 'started' not in events:
                notifier.send(f'Starting {kind} rollcall\n{context}')
                events.add('started')
            submitted = 'Answer submitted; awaiting server confirmation'
            if item.is_number:
                details = client.student_rollcall(rcid)
                client.answer_num(rcid, details.number_code)
                submitted += f'\nCode: {details.number_code}'
            else:
                client.answer_radar(rcid)
            logging.info('ID: %s answer submitted; awaiting server confirmation', rcid)
            if 'submitted' not in events:
                notifier.send(f'{submitted}\n{context}')
                events.add('submitted')
        except Exception as error:
            logging.exception('ID: %s rollcall failed', rcid)
            if 'failed' not in events:
                notifier.send(f'Rollcall failed ({type(error).__name__}); will retry\n{context}')
                events.add('failed')


def run(config):
    notifier = Notifier(config)
    client = Tronclass(config)
    try:
        client.login()
    except Exception as error:
        notifier.send(f'Login failed ({type(error).__name__})')
        raise
    notifier.send('Login succeeded')
    working = False
    checking_failed = False
    notified_events = {}
    while True:
        now = datetime.now()
        schedule = config.operating[now.weekday()]
        if not schedule.enable:
            if working:
                notifier.send('Off working day')
            working = False
            logging.info('off working day; sleep...')
            time.sleep(3600)
            continue

        start, end = [datetime.strptime(t, '%H:%M').time() for t in schedule.range]
        if not start <= now.time() <= end:
            if working:
                logging.info('off working time')
                notifier.send('Off working time')
            working = False
            logging.debug('sleep...')
            time.sleep(300)
            continue

        if not working:
            logging.info('starting working')
            notifier.send('Starting working')
            working = True
        try:
            logging.debug('%s - checking', client.counter)
            check_rollcalls(client, notified_events, notifier)
            if checking_failed:
                notifier.send('Rollcall checking has been restored')
                checking_failed = False
        except Exception as error:
            logging.exception('rollcall check failed')
            if not checking_failed:
                notifier.send(f'Rollcall check failed ({type(error).__name__}); will retry')
                checking_failed = True

        client.counter += 1
        time.sleep(config.config.Senkaku)


def main(argv=None):
    parser = argparse.ArgumentParser(description='TronClass attendance client')
    parser.add_argument('-c', '--config', type=Path, help='Path to config file')
    parser.add_argument('-l', '--log', type=Path, help='Root directory for logs stored as year/month/day.log')
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
