import requests
import random 
import string
import re
import json
from ddddocr import DdddOcr
from tenacity import retry ,wait_random
import logging

from schemas import *

class LoginFaild(Exception):
    def __init__(self, message='Login Failed!'):
        super().__init__(message)

class Tronclass:
    TRON = 'https://tronclass.ntou.edu.tw'
    CAPTCAHJPG = 'https://tccas.ntou.edu.tw/cas/captcha.jpg'
    PATTERN = re.compile(r'(LT[^"]+)')
    OCR = DdddOcr(show_ad=False)

    def __init__(self, account, config):
        logging.debug("start init client")
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
        logging.debug('init complete')


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

    # ntou's special login flow 
    # replace this function yourself if you want use it for in aother school
    @retry(
        stop=lambda rs: rs.attempt_number >= int(rs.args[0].CONFIG['retries']),
        wait=wait_random(min=1, max=1),
        reraise=True
    )
    def login(self) -> None:
        logging.info(f'start login as {self.USER} | {self.counter}') 
        self.counter += 1
        self.set_session()

        # get LT-xxxxx token and save redirect url
        lt_page = self.session.get(
            url=f'{Tronclass.TRON}/login?next=/user/index'
        )
        lt = Tronclass.PATTERN.search(lt_page.text).group(0)

        # using ocr to get captcha
        rawtxt = self.OCR.classification(
            self.session.get(
                url=Tronclass.CAPTCAHJPG
            ).content
        )
        captcah = re.sub(r'[^0-9]', '', rawtxt)

        payload = {
            'username': self.USER,
            'password': self.PASSWD,
            'captcha': captcah,
            'lt': lt,
            'execution': 'e1s1',
            '_eventId': 'submit',
            'submit': '登錄'
        }

        resp = self.session.post(
            url=lt_page.url,
            data=payload
        )
        if 'forget-password' in resp.text:
            logging.warning(f'{e} | {self.counter}')
            raise LoginFaild()

        logging.info('login successed')
        return


# -------------------------------------------
# Pure API Endpoints
# -------------------------------------------
    @retry(
        stop=lambda rs: rs.attempt_number >= int(rs.args[0].CONFIG['retries']), wait=wait_random(min=1, max=1), reraise=True
    )
    def re_visited(self) -> VisitedCourses:
        resp = self.session.get(
            url = f'{Tronclass.TRON}/api/user/recently-visited-courses'
        )
        return VisitedCourses.model_validate_json(resp.text)

    @retry(
        stop=lambda rs: rs.attempt_number >= int(rs.args[0].CONFIG['retries']), wait=wait_random(min=1, max=1), reraise=True
    )
    def rollcall(self) -> Rollcall:
        resp = self.session.get(
            url=f'{Tronclass.TRON}/api/radar/rollcalls?api_version=1.1.0'
        )
        return Rollcall.model_validate_json(resp.text)

    @retry(
        stop=lambda rs: rs.attempt_number >= int(rs.args[0].CONFIG['retries']), wait=wait_random(min=1, max=1), reraise=True
    )
    def student_rollcall(self, rcid:str | None = None) -> StudentRollcall:
        # to get 
        # test case 2145183
        id = rcid if rcid else self.rcid
        resp = self.session.get(
            url = f'{Tronclass.TRON}/api/rollcall/{id}/student_rollcalls'
        )
        ret = StudentRollcall.model_validate_json(resp.text)
        self.num_code = ret.number_code
        logging.info(f'rollcall ID: {id}, code: {ret.number_code}')
        return ret

    @retry(
        stop=lambda rs: rs.attempt_number >= int(rs.args[0].CONFIG['retries']), wait=wait_random(min=1, max=1), reraise=True
    )
    def answer_num(self, rcid:str|None = None, code:str|None = None) -> dict:
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
    def answer_radar(self, rcid:str | None = None) -> dict:
        id = rcid if rcid else self.rcid
        resp = self.session.put(
            url=f'{Tronclass.TRON}/api/rollcall/{id}/answer',
            json={}
        )
        return json.loads(resp.text)
    
    @retry(
        stop=lambda rs: rs.attempt_number >= int(rs.args[0].CONFIG['retries']), wait=wait_random(min=1, max=1), reraise=True
    )
    def anser_regi(self, rcid:str | None = None) -> dict:
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

