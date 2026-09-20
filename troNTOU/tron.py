import requests
import random 
import string
import re
import json
from tenacity import retry ,wait_random

from pytesseract import image_to_string, pytesseract
from PIL import Image
from io import BytesIO


class LoginFaild(Exception):
    def __init__(self, message='Login Failed!\n'):
        super().__init__(message)

class Tronclass:
    TRON = 'https://tronclass.ntou.edu.tw'
    PATTERN = re.compile(r'(LT[^"]+)')
    CAPTCAHJPG = 'https://tccas.ntou.edu.tw/cas/captcha.jpg'

    # enable if this script run on windows
    pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

    def __init__(self, account, config):
        self.USER = account['user']
        self.PASSWD = account['passwd']
        self.CONFIG = config

        self.counter = 0
        self.device_id = ''.join(
            random.choices(string.ascii_letters+string.digits, k=16)
        )

        self.session: requests.Session
        self.rcid: int
        self.num_code: int


    def set_session(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': random.choice([
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.5410.0 Safari/537.36',
                'Mozilla/5.0 (Android 10; Mobile; rv:78.0) Gecko/20100101 Firefox/78.0',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:83.0) Gecko/20100101 Firefox/83.0',
                'Mozilla/5.0 (SymbianOS/9.4; Series60/5.0 NokiaN97-1/20.0.019; Profile/MIDP-2.1 Configuration/CLDC-1.1) AppleWebKit/525 (KHTML, like Gecko) BrowserNG/7.1.18124'   
            ]),
            'Accept': (
                'text/html,application/xhtml+xml,'
                'application/xml;q=0.9,*/*;q=0.8'
            ),
            'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
        })
        self.session.hooks["response"].append(
            lambda response, *args, **kwargs: response.raise_for_status()
        )

    @retry(
        stop=lambda rs: rs.attempt_number >= int(rs.args[0].CONFIG['retries']),
        wait=wait_random(min=1, max=1),
        reraise=True
    )
    def login(self) -> None:
        self.counter += 1
        try:
            self.set_session()
            
            lt_page = self.session.get(
                url=f'{Tronclass.TRON}/login?next=/user/index'
            )
            lt = Tronclass.PATTERN.search(lt_page.text).group(0)

            jpg = self.session.get(
                url=Tronclass.CAPTCAHJPG
            )
            captcha = Image.open(BytesIO(jpg.content)).convert('L')
            text = re.sub(r'[^0-9]', '', image_to_string(
                captcha,
                config='-c tessedit_char_whitelist=0123456789 --psm 8')
            )

            data = {
                'username': self.USER,
                'password': self.PASSWD,
                'captcha': text,
                'lt': lt,
                'execution': 'e1s1',
                '_eventId': 'submit',
                'submit': '登錄'
            }

            resp = self.session.post(
                url=lt_page.url,
                data=data
            )
            if 'forget-password' in resp.text:
                raise LoginFaild()

            return

        except LoginFaild as e:
            print(f'{e} | {self.counter}\n')
            raise

        except Exception as e:
            print(f'{e} | {self.counter}\n')

    ### pure api endpoint
    @retry(
        stop=lambda rs: rs.attempt_number >= int(rs.args[0].CONFIG['retries']), wait=wait_random(min=1, max=1), reraise=True
    )
    def re_visited(self) -> str:
        resp = self.session.get(
            url = f'{Tronclass.TRON}/api/user/recently-visited-courses'
        )
        return json.loads(resp.text)
    
    @retry(
        stop=lambda rs: rs.attempt_number >= int(rs.args[0].CONFIG['retries']), wait=wait_random(min=1, max=1), reraise=True
    )
    def rollcall(self) -> dict:
        resp = self.session.get(
            url=f'{Tronclass.TRON}/api/radar/rollcalls?api_version=1.1.0'
        )
        return json.loads(resp.text)

    @retry(
        stop=lambda rs: rs.attempt_number >= int(rs.args[0].CONFIG['retries']), wait=wait_random(min=1, max=1), reraise=True
    )
    def num_code(self, rcid:str = None) -> dict:
        id = rcid if rcid else self.rcid
        resp = self.session.get(
            url = f'{Tronclass.TRON}/api/rollcall/{id}/student_rollcalls'
        )
        data = json.loads(self.get_num_ans())
        self.code = data['number_code']
        
        return data

    @retry(
        stop=lambda rs: rs.attempt_number >= int(rs.args[0].CONFIG['retries']), wait=wait_random(min=1, max=1), reraise=True
    )
    def answer_num(self, rcid=None, code=None) -> dict:
        id = rcid if rcid else self.rcid
        ans = code if code else self.num_code
        resp = self.session.put(
            url=f'{Tronclass.TRON}/api/rollcall/{id}/answer_number_rollcall',
            json={
                "deviceId": self.device_id,
                "numberCode": ans
            }
        )
        return json.loads(resp.text)

    @retry(
        stop=lambda rs: rs.attempt_number >= int(rs.args[0].CONFIG['retries']), wait=wait_random(min=1, max=1), reraise=True
    )
    def answer_radar(self, rcid=None) -> dict:
        id = rcid if rcid else self.rcid
        resp = self.session.put(
            url=f'{Tronclass.TRON}/api/rollcall/{id}/answer',
            json={}
        )
        return json.loads(resp.text)
    
    @retry(
        stop=lambda rs: rs.attempt_number >= int(rs.args[0].CONFIG['retries']), wait=wait_random(min=1, max=1), reraise=True
    )
    def anser_regi(self, rcid=None) -> dict:
        id = rcid if rcid else self.rcid
        resp = self.session.put(
            url=f'{Tronclass.TRON}/api/rollcall/{id}/answer_self_registration_rollcall',
            json={}
        )
        return json.loads(resp.text)

    # resource
    # @retry(
    #     stop=lambda rs: rs.attempt_number >= int(rs.args[0].CONFIG['retries']), wait=wait_random(min=1, max=1), reraise=True
    # )

    # def resources(self, page='1', size='20'):
    #     payload = {
    #         "conditions": {
    #             "keyword":"",
    #             "includeSlides":"false",
    #             "limitTypes":
    #                 [
    #                     "file","video","document","image","audio","scorm","evercam","swf","wmpkg","link"
    #                 ],
    #             "fileType":"all",
    #             "parentId":0,
    #             "sourceType":"MyResourcesFile",
    #             "no-intercept":"true"
    #         },
    #         "page": page,
    #         "page_size": size
    #     }
    #     resp = self.session.get(
    #         url=f'{Tronclass.TRON}/api/usr/resources',
    #         params=payload
    #     )    
    #     return json.loads(resp.text)

