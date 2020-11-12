import json
import os
from base64 import b64encode
from concurrent.futures.thread import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Union

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from utils.botConfig import settings
from utils.decorators import CatchRequestsException
from utils.exception import BotRequestError
from utils.network import NetworkUtils
from utils.objects import convertImageFormat
from utils.tmpFile import tmpFile

from .config import Config

Executor = ThreadPoolExecutor(settings.THREAD_POOL_NUM)
APIresult_T = Union[List[Dict[str, Any]], Dict[str, Any]]


@CatchRequestsException(prompt="下载图片失败", retries=Config.apis.retries)
def downloadImage(url: str, mosaic: Optional[bool] = False) -> str:
    headers = {"Referer": "https://www.pixiv.net"}
    r = requests.get(url, headers=headers, timeout=(6, 12), proxies=NetworkUtils.proxy)
    r.raise_for_status()
    if mosaic:
        pngImage = mosaicImage(r.content)
    else:
        pngImage = convertImageFormat(r.content)
    return f"base64://{b64encode(pngImage).decode()}"


def textAlign(
    img: bytes,
    text: str,
    font: Optional[str] = "./data/font.otf",
    fontSize: Optional[int] = 100,
    fontColor: Optional[str] = "#FF0000",
) -> bytes:
    with tmpFile() as tf:
        with open(tf, "wb") as f:
            f.write(img)
        with Image.open(tf) as im:
            imageFont = ImageFont.truetype(font=font, size=fontSize)
            imageWidth, imageHeight = im.size
            textWidth, textHeight = imageFont.getsize(text)
            imageDraw = ImageDraw.Draw(im)
            textCoordinate = [
                (imageWidth - textWidth) / 2,
                (imageHeight - textHeight) / 2,
            ]
            imageDraw.text(xy=textCoordinate, text=text, fill=fontColor, font=imageFont)
            im.save(tf, "PNG")
        with open(tf, "rb") as f:
            fileRead = f.read()
    return fileRead


def mosaicImage(img: bytes) -> bytes:
    with tmpFile() as tf:
        with open(tf, "wb") as f:
            f.write(img)
        with Image.open(tf) as im:
            blured = im.filter(ImageFilter.GaussianBlur(radius=10))
            blured.save(tf, "PNG")
        with open(tf, "rb") as f:
            fileRead = f.read()
    imageWithText = textAlign(fileRead, "R-18")
    return convertImageFormat(imageWithText)


def downloadMutliImage(
    urls: List[str], mosaic: Optional[bool] = False
) -> Dict[str, bytes]:
    download = Executor.map(lambda x: downloadImage(*x), [(i, mosaic) for i in urls])
    return dict(zip(urls, download))


class pixiv:
    @CatchRequestsException(prompt="从Pixiv获取接口信息失败")
    def _baseGetJSON(params: Dict[str, str]) -> APIresult_T:
        r = requests.get(Config.apis.address, params=params, timeout=3)
        r.raise_for_status()
        resp: dict = r.json()
        if resp.get("error"):
            reason = "".join([str(i) for i in resp["error"].keys() if i])
            raise BotRequestError(reason)
        return resp

    @classmethod
    def getRank(cls, rankLevel: Optional[str] = "week") -> APIresult_T:
        argsPayload = {"type": "rank", "mode": rankLevel}
        getData = cls._baseGetJSON(argsPayload)
        return getData

    @classmethod
    def searchIllust(
        cls,
        keyword: str,
        page: Optional[int] = 1,
        searchMode: Optional[int] = 0,
        ascending: Optional[bool] = False,
    ) -> APIresult_T:
        searchModeString = (
            "partial_match_for_tags"
            if searchMode == 0
            else "exact_match_for_tags"
            if searchMode == 1
            else "title_and_caption"
        )
        argsPayload = {
            "type": "search",
            "word": keyword,
            "mode": searchModeString,
            "page": page,
            "order": "date_asc" if ascending else "date_desc",
        }
        getData = cls._baseGetJSON(argsPayload)
        return getData

    @classmethod
    def getRelatedIllust(cls, imageID: int) -> APIresult_T:
        argsPayload = {"type": "related", "id": str(imageID)}
        getData = cls._baseGetJSON(argsPayload)
        return getData

    @classmethod
    def getHotTags(cls) -> APIresult_T:
        argsPayload = {"type": "tags"}
        getData = cls._baseGetJSON(argsPayload)
        return getData

    @classmethod
    def getImageDetail(cls, imageID: int) -> APIresult_T:
        argsPayload = {"type": "illust", "id": str(imageID)}
        getData = cls._baseGetJSON(argsPayload)
        return getData

    @classmethod
    def getMemberDetail(cls, memberID: int) -> APIresult_T:
        argsPayload = {"type": "member", "id": str(memberID)}
        getData = cls._baseGetJSON(argsPayload)
        return getData

    @classmethod
    def getMemberIllust(cls, memberID: int, page: Optional[int] = 1) -> APIresult_T:
        argsPayload = {"type": "member_illust", "id": str(memberID), "page": str(page)}
        getData = cls._baseGetJSON(argsPayload)
        return getData


class cache:
    _path = "./data/PixivCache.json"

    @classmethod
    def all(cls) -> APIresult_T:
        cacheData = {}
        if not os.path.isfile(cls._path):
            return cacheData
        with open(cls._path, "rt", encoding="utf-8") as f:
            cacheData = json.load(f)
        return cacheData

    @classmethod
    def read(cls, name: str) -> APIresult_T:
        cacheData = cls.all()
        if name not in cacheData:
            raise BotNotFoundError("缓存未命中")
        return cacheData[name]

    @classmethod
    def update(cls, name: str, data: APIresult_T) -> int:
        cacheData = cls.all()
        cacheData[name] = data
        with open(cls._path, "wt", encoding="utf-8") as f:
            totalWrite = f.write(json.dumps(cacheData))
        return totalWrite
