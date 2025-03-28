import requests
import re
import time 
import json
import yaml
from pathlib import Path
from datetime import datetime

tron = 'https://tronclass.ntou.edu.tw'
session = requests.session()
sercret = []

header = {
    'Accpet': 'application/json, text/plain, */*',
    'Content-Type': 'application/json',
    'Accept-Language': 'en-US'
}

def re_visited():
    response  = session.get(url=tron+'/api/user/recently-visited-courses')
    response.encoding = 'utf-8'
    data = {
        'status_code': response.status_code,
        'headers': response.headers,
        'body': response.json()

    }
    print(data)

def log(path: Path, cnt: int, response: requests.models.Response):
    data = {
        'status_code': response.status_code,
        'body': response.json()
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a', encoding='utf-8') as file:
        file.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | total: {cnt}\n")
        file.write(json.dumps(data, ensure_ascii=False, indent=2))
        file.write('\n\n') 



def login():
    login_page = session.get(url=f'{tron}/login?next=/user/index')

    # re_lt = re.compile(r'(LT[^"]+)')
    # lt = re_lt.search(login.text).group(0)
    user_inf = {
        'username': config['accont']['user'],  
        'password': config['accont']['passwd'],
        'lt': re.search(r'(LT[^"]+)', login_page.text).group(0),
        'execution': 'e1s1',
        '_eventId': 'submit',
        'submit': '登錄'
    }

    session.post(url=login_page.url, data=user_inf)
    # print(tmp.status_code) 
    re_visited()


def try_num(id):
    for i in range(10000):
        payload = { 
            # 'deviceId': sercret[2],
            'deviceId': config['phoneID'],
            'numberCode': str(i).zfill(4)
        }

        try: 
            response = session.put(url=f'{tron}/api/rollcall/{id}/answer_number_rollcall', json=payload)
            response.raise_for_status()
            print('num, on_call ', response)
        except requests.exceptions.RequestException as e:
            print(e)
        finally:
            log(Path('log')/'num_test'/f'{id}.log', i, response)



def main():
    cnt = 0
    while True:
        response = session.get(url=tron+'/api/radar/rollcalls?api_version=1.1.0')
        response.encoding = 'utf-8'
        data: dict = response.json()

        log(Path('log')/'main.log', cnt, response)

        if  data.get('rollcalls'):
            rollcall: dict = data['rollcalls'][0]
            rollcall_id = rollcall.get('rollcall_id')
            if rollcall.get('is_number'):
                try_num(rollcall_id)
                print('end_num')
            elif rollcall.get('is_radar'):
                print('is_radar')

        else:
            print(cnt, 'not call')

        cnt = cnt + 1
        time.sleep(180)
        
if __name__ == '__main__':
    with open('config.yaml', 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)

    login()
    main()
