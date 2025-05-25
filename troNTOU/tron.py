import aiohttp
import yaml
import asyncio
import time
import re
import json
import random
import string 
from datetime import datetime
from pathlib import Path
from sys import exit


TRON = 'https://tronclass.ntou.edu.tw'
PATH = Path('log')
PATTERN = re.compile(r'(LT[^"]+)')
with open(Path(__file__).parent.parent / 'config.yaml', 'r', encoding='utf-8') as file:
    config = yaml.safe_load(file)
USER = config['account']['user']
PAWD = config['account']['passwd']
ELOG = config['config']['enable_log']
GAP = config['config']['Senkaku']
RETRIES = config['config']['retries']
UA = config['config']['user-agent']

class LoginFaild(Exception):
    def __init__(self, message='Login failed!'):
        super().__init__(message)

def random_id() -> str:
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=16))

def log(path:Path, resp:tuple[str, int, dict], cnt:int = -1) -> bool:
    if not ELOG:
        return False

    try:
        data = {
            'request': resp[0],
            'status_code': resp[1],
            'body': resp[2]
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'a', encoding='utf-8') as file:
            file.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {cnt}\n")
            file.write(json.dumps(data, ensure_ascii=False, indent=2))
            file.write('\n') 
    except Exception as e:
        print(e)
        return False
    return True

async def login(id:int = 0) -> aiohttp.ClientSession:
    for attempt in range(RETRIES):
        session = None
        try:
            session = aiohttp.ClientSession(headers={
                'User-Agent': UA
            })
            async with session.get(url=f'{TRON}/login?next=/user/index') as page:
                lt = PATTERN.search(await page.text()).group(0)
            data = {
                'username': USER,
                'password': PAWD,
                'lt': lt,
                'execution': 'e1s1',
                '_eventId': 'submit',
                'submit': '登錄'
            }

            async with session.post(url=page.url, data=data) as response:
                if 'forget-password' in await response.text():
                    raise LoginFaild()
            return session

        except LoginFaild as e:
            await session.close()
            if attempt < RETRIES:
                print(f'login {id} | retry attempt {attempt}')
            else:
                print('Max retries reached! login failed')
                print('username or password may be incorrect\n' \
                'check password!\n')
                return None
        except Exception as e:
            await session.close()
            print(f'login {id} | {e}')
            return None


async def re_visited() -> aiohttp.ClientResponse:
    async with await login() as session:
        resp = await session.get(f'{TRON}/api/user/recently-visited-courses')
        return resp

async def number(rcid: int, ses:int = 25, ran:int = 400) -> int:
    async def inner(ses_id:int):
        nonlocal succeed, code
        async with await login(ses_id) as session:
            for i in range(ran):
                payload = {
                    'deviceId': device,
                    'numberCode': f'{ses_id*ran+i:04d}'
                }
                try:
                    async with await session.put(
                        f'{TRON}/api/rollcall/{rcid}/answer_number_rollcall',
                        json=payload
                    ) as resp:
                        json: dict = await resp.json(encoding='utf-8')
                        log(PATH/'num'/f'{rcid}.log', (str(resp.url), resp.status, json), ses_id*ran+i)
                        succeed = succeed + 1
                        resp.raise_for_status()
                        code = f'{ses_id*ran+i:04d}'
                except aiohttp.ClientResponseError as e:
                    if e.status == 400:
                        print(e.status)
                    else:
                        raise
                except Exception as e:
                    print(e)
    succeed = 0
    code = -1
    device = random_id()
    tasks = [inner(i) for i in range(ses)]

    start = time.perf_counter()
    await asyncio.gather(*tasks)
    spend = time.perf_counter()-start

    log(PATH/'num'/f'{rcid}.log', ('summary', code, dict(
        spend_time = spend,
        succeed_cnt = succeed,
        opened_session = ses,
        requeset_per_session = ran
    )))
    print(spend, code)
    return code

async def check_rollcall(cnt:int = -1) -> int:
    async with await login(cnt) as session:
        async with session.get(f'{TRON}/api/radar/rollcalls?api_version=1.1.0') as resp:
            json: dict = await resp.json(encoding='utf-8')
            today = datetime.now()
            y = str(today.year)
            m = str(today.month)
            d = str(today.day)
            log(PATH/y/m/f'{d}.log', (str(resp.url), resp.status, json), cnt)

            if json.get('rollcalls'):
                rollcall: dict = json['rollcalls'][0]
                if rollcall.get('status') == 'on_call_fine':
                    print('rollcalled')
                    status = 0

                elif rollcall.get('is_number'):
                    print('start num')
                    id = rollcall.get('rollcall_id')
                    await number(id)
                    status = 1

                elif rollcall.get('is_radar'):
                    print('start loc')
                    status = 2
            else:
                print('not call')        
                status = -1
        return status

async def test_login():
    async with aiohttp.ClientSession(headers={
        'User-Agent': UA
    }) as session:
        async with session.get(url=f'{TRON}/login?next=/user/index') as page:
            lt = PATTERN.search(await page.text()).group(0)
        
        try:
            async with session.post(url=page.url, data={
                'username': USER,
                'password': PAWD,
                'lt': lt,
                'execution': 'e1s1',
                '_eventId': 'submit',
                'submit': '登錄'
            }) as resp:
                if 'forget-password' in await resp.text():
                    raise LoginFaild()
                ua = resp.request_info.headers.get('User-Agent')
            s =  f'login succeed\nuser: {USER}\n---------------------'
            print(ua)
            print(s)
            return
        except LoginFaild as e:
            s = 'username or password may be incorrect\n' \
            'check password!'
            print(s)
            exit()

async def qps(id:int = -1) -> bool:
    async def inner(ses_id:int):
        nonlocal succeed, sent, received
        async with await login(ses_id) as session:
            for i in range(ran):
                try:
                    async with await session.get(
                        f'{TRON}/api/user/recently-visited-courses'
                    ) as resp:
                        # json: dict = await resp.json(encoding='utf-8')
                        json = dict(ok='ok')
                        log(PATH/'qps'/f'{id}.log', (str(resp.url), resp.status, json), ses_id*ran+i)
                        succeed = succeed + 1
                        sent += int(resp.request_info.headers.get('Content-Length') or 0)
                        received += len(await resp.read())
                except Exception as e:
                    print(e)
    
    succeed = 0
    ses = 25
    ran = 400
    sent = 0
    received = 0
    tasks = [inner(i) for i in range(ses)]
    print('start QPS testing')

    start = time.perf_counter()
    await asyncio.gather(*tasks)
    spend = time.perf_counter() - start

    log(PATH/'qps'/f'{id}.log', ('summary', succeed, dict(
        spend_time = spend,
        open_session = ses, 
        request_per_session = ran,
        total_bytes_sent = sent,
        total_bytes_received = received
    )))
    print('done\nt:', spend)
    return

async def main():
    await test_login()
    cnt = 0
    while True:
        print(cnt, end=' ')
        await check_rollcall(cnt)
        # await qps(cnt) 
        cnt = cnt + 1
        await asyncio.sleep(GAP)

if __name__ == "__main__":
    # asyncio.run(qps())
    # asyncio.run(test_login())
    asyncio.run(main())
