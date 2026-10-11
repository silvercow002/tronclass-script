import requests
import random 
import string
import re
import json
from ddddocr import DdddOcr
from tenacity import retry, retry_if_exception_type, wait_random
import logging

from schemas import *

class LoginFaild(Exception):
    def __init__(self, message='Login Failed!'):
        super().__init__(message)


def stop_after_configured_attempts(retry_state):
    return retry_state.attempt_number >= retry_state.args[0].config.config.retries


retry_request = retry(
    stop=stop_after_configured_attempts,
    wait=wait_random(min=1, max=1),
    retry=retry_if_exception_type((requests.RequestException, LoginFaild)),
    reraise=True,
)


class Tronclass:
    TRON = 'https://tronclass.ntou.edu.tw'
    CAPTCAHJPG = 'https://tccas.ntou.edu.tw/cas/captcha.jpg'
    PATTERN = re.compile(r'(LT[^"]+)')
    REQUEST_TIMEOUT = (10, 30)
    OCR = DdddOcr(show_ad=False)

    def __init__(self, config):
        logging.debug("start init client")
        self.config:Config = config

        self.counter = 0
        self.device_id = ''.join(
            random.choices(string.ascii_letters+string.digits, k=16)
        )

        self.session: requests.Session | None = None
        self.rcid: int | str | None = None
        self.num_code: str | None = None
        self.ocr = self.OCR
        logging.debug('init complete')


    def set_session(self):
        if self.session is not None:
            self.session.close()
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
    @retry_request
    def login(self) -> None:
        logging.info('start login as ***%s | %s', self.config.account.user[-3:], self.counter)
        self.counter += 1
        self.set_session()

        # get LT-xxxxx token and save redirect url
        lt_page = self.session.get(
            url=f'{Tronclass.TRON}/login?next=/user/index',
            timeout=self.REQUEST_TIMEOUT,
        )
        lt_match = Tronclass.PATTERN.search(lt_page.text)
        lt = lt_match.group(0)

        # using ocr to get captcha
        rawtxt = self.ocr.classification(
            self.session.get(
                url=Tronclass.CAPTCAHJPG,
                timeout=self.REQUEST_TIMEOUT,
            ).content
        )
        captcah = re.sub(r'[^0-9]', '', rawtxt)

        payload = {
            'username': self.config.account.user,
            'password': self.config.account.passwd,
            'captcha': captcah,
            'lt': lt,
            'execution': 'e1s1',
            '_eventId': 'submit',
            'submit': '登錄'
        }

        resp = self.session.post(
            url=lt_page.url,
            data=payload,
            timeout=self.REQUEST_TIMEOUT,
        )
        if 'forget-password' in resp.text:
            logging.warning('login rejected | %s', self.counter)
            raise LoginFaild()

        logging.info('login succeeded')
        return


# -------------------------------------------
# Pure API Endpoints
# -------------------------------------------
    @retry_request
    def re_visited(self) -> VisitedCourses:
        resp = self.session.get(
            url = f'{Tronclass.TRON}/api/user/recently-visited-courses',
            timeout=self.REQUEST_TIMEOUT,
        )
        ret = VisitedCourses.model_validate_json(resp.text)
        logging.debug(ret)
        return ret

    @retry_request
    def rollcall(self) -> Rollcall:
        resp = self.session.get(
            url=f'{Tronclass.TRON}/api/radar/rollcalls?api_version=1.1.0',
            timeout=self.REQUEST_TIMEOUT,
        )
        ret = Rollcall.model_validate_json(resp.text)
        logging.debug(ret)
        return ret

    @retry_request
    def student_rollcall(self, rcid:int | str | None = None) -> StudentRollcall:
        id = rcid if rcid else self.rcid
        self.rcid = id
        self.num_code = None
        resp = self.session.get(
            url = f'{Tronclass.TRON}/api/rollcall/{id}/student_rollcalls',
            timeout=self.REQUEST_TIMEOUT,
        )
        ret = StudentRollcall.model_validate_json(resp.text)
        self.num_code = ret.number_code
        logging.debug('loaded number code for rollcall ID: %s', id)
        return ret

    @retry_request
    def answer_num(self, rcid:int | str | None = None, code:str | None = None) -> dict:
        id = rcid if rcid else self.rcid
        ans = code if code is not None else self.num_code if id == self.rcid else None
        if not ans:
            raise ValueError('A number code for this rollcall is required')
        resp = self.session.put(
            url=f'{Tronclass.TRON}/api/rollcall/{id}/answer_number_rollcall',
            json={
                "deviceId": self.device_id,
                "numberCode": ans
            },
            timeout=self.REQUEST_TIMEOUT,
        )
        return json.loads(resp.text)

    @retry_request
    def answer_radar(self, rcid:int | str | None = None) -> dict:
        id = rcid if rcid else self.rcid
        resp = self.session.put(
            url=f'{Tronclass.TRON}/api/rollcall/{id}/answer',
            json={},
            timeout=self.REQUEST_TIMEOUT,
        )
        return json.loads(resp.text)
    
    @retry_request
    def anser_regi(self, rcid:int | str | None = None) -> dict:
        id = rcid if rcid else self.rcid
        resp = self.session.put(
            url=f'{Tronclass.TRON}/api/rollcall/{id}/answer_self_registration_rollcall',
            json={},
            timeout=self.REQUEST_TIMEOUT,
        )
        return json.loads(resp.text)

    # resource
    # @retry_request

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

