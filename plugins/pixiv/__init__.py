import random
from secrets import token_hex
from typing import List

from nonebot import CommandSession, MessageSegment, on_command
from nonebot.command.argfilter.extractors import extract_numbers, extract_text
from nonebot.permission import GROUP_ADMIN, PRIVATE_FRIEND, SUPERUSER

from utils.decorators import SyncToAsync, WithKeyword
from utils.manager import PluginManager, nameJoin
from utils.message import processSession

from .config import Config
from .parse import parseMultiImage, parseSingleImage
from .tools import cache, downloadMutliImage, pixiv

__plugin_name__ = "pixiv"

GET_IMAGE_METHOD = nameJoin(__plugin_name__, "get")
SEARCH_IMAGE_METHOD = nameJoin(__plugin_name__, "search")
MEMBER_IMAGE_METHOD = nameJoin(__plugin_name__, "member")
RANK_IMAGE_METHOD = nameJoin(__plugin_name__, "rank")
OPERATING_METHOD = nameJoin(__plugin_name__, "ops")
POWER_GROUP = GROUP_ADMIN | SUPERUSER | PRIVATE_FRIEND

PluginManager.registerPlugin(GET_IMAGE_METHOD, defaultSettings={"r-18": False})
PluginManager.registerPlugin(SEARCH_IMAGE_METHOD, defaultSettings={"r-18": False})
PluginManager.registerPlugin(MEMBER_IMAGE_METHOD, defaultSettings={"r-18": False})
PluginManager.registerPlugin(RANK_IMAGE_METHOD)
PluginManager.registerPlugin(OPERATING_METHOD)

_RANK_CACHE = {}


@on_command(GET_IMAGE_METHOD, aliases=("点图", "获取图片"))
@processSession(pluginName=GET_IMAGE_METHOD)
@WithKeyword("p站点图", command=GET_IMAGE_METHOD)
@SyncToAsync
def getImage(session: CommandSession):
    allowR18: bool = PluginManager.settings(GET_IMAGE_METHOD, ctx=session.ctx).settings[
        "r-18"
    ]
    imageID: int = session.get("id")
    imageResloution: str = session.get_optional("res", "large")
    session.send(f"开始获取Pixiv ID为{imageID}的{imageResloution}")
    apiGet = pixiv.getImageDetail(imageID)
    apiParse = parseSingleImage(apiGet, mosaicR18=not allowR18)
    imageURLs = [p[imageResloution] for p in apiParse["download"]][
        : Config.customize.size
    ]
    imageDownloaded = downloadMutliImage(
        imageURLs, mosaic=((not allowR18) and apiParse["r-18"])
    )
    images = [str(MessageSegment.image(imageDownloaded[i])) for i in imageURLs]
    repeatMessage = "\n".join(images)
    finalMessage = (
        str(Config.customize.image_prefix).format(**apiParse)
        + f"{repeatMessage}\n"
        + str(Config.customize.image_suffix).format(**apiParse)
    )
    return finalMessage


@getImage.args_parser
@processSession(pluginName=GET_IMAGE_METHOD)
@SyncToAsync
def _(session: CommandSession):
    numberArgs = extract_numbers(session.current_arg_text)
    textArgs = extract_text(session.current_arg_text)
    if not numberArgs:
        session.pause("请输入p站图片ID")
    session.state["id"] = int(numberArgs[0])
    keywordChoice = {
        "大图": "large",
        "小图": "medium",
        "原图": "original",
    }
    for key, value in keywordChoice.items():
        if key in textArgs:
            session.state["res"] = value
            break


@on_command(SEARCH_IMAGE_METHOD, aliases=("p站搜图", "搜索图片"))
@processSession(pluginName=SEARCH_IMAGE_METHOD)
@WithKeyword("p站搜图", command=SEARCH_IMAGE_METHOD)
@SyncToAsync
def searchImage(session: CommandSession):
    enableR18 = PluginManager.settings(SEARCH_IMAGE_METHOD, session.ctx).settings[
        "r-18"
    ]
    keywords = session.get("keyword")
    page = session.get_optional("page", 1)
    session.send(f'开始搜索"{keywords}"的第{page}页')
    apiGet = pixiv.searchIllust(keyword=keywords, page=page)
    apiParse = parseMultiImage(apiGet, mosaicR18=not enableR18)
    sortResult = sorted(apiParse["result"], key=lambda x: x["ratio"], reverse=True)
    messageRepeat = [
        str(Config.customize.search_repeat).format(**data) for data in sortResult
    ]
    fullMessage = (
        str(Config.customize.search_prefix).format(**apiParse)
        + "".join(messageRepeat[: Config.customize.size])
        + str(Config.customize.search_suffix).format(**apiParse)
    )
    return fullMessage


@searchImage.args_parser
@processSession(pluginName=SEARCH_IMAGE_METHOD)
@SyncToAsync
def _(session: CommandSession):
    if session.current_arg_images:
        session.switch(f"!{GET_IMAGE_METHOD} {session.current_arg}")
    strippedArgs = session.current_arg_text.strip()
    if not strippedArgs:
        session.pause("请输入搜索关键词")
    keywords: List[str] = strippedArgs.split(" ")
    if len(keywords) >= 2:
        if keywords[0].isdigit():
            session.state["page"] = int(keywords[0])
            keywords.pop(0)
    session.state["keyword"] = " ".join(keywords)


@on_command(MEMBER_IMAGE_METHOD, aliases=("p站画师", "画师", "搜索画师"))
@processSession(pluginName=MEMBER_IMAGE_METHOD)
@WithKeyword("p站画师", "搜索画师")
@SyncToAsync
def memberImage(session: CommandSession):
    memberID = session.get("id")
    enableR18 = PluginManager.settings(MEMBER_IMAGE_METHOD, session.ctx).settings[
        "r-18"
    ]
    page = session.get_optional("page", 1)
    session.send(f"开始获取Pixiv用户ID为{memberID}的作品第{page}页")
    apiGet = pixiv.getMemberIllust(memberID, page)
    apiParse = parseMultiImage(apiGet, mosaicR18=not enableR18)
    sortResult = sorted(apiParse["result"], key=lambda x: x["ratio"], reverse=True)
    messageRepeat = [
        str(Config.customize.member_repeat).format(**data) for data in sortResult
    ]
    fullMessage = (
        str(Config.customize.member_prefix).format(**apiParse)
        + "".join(messageRepeat[: Config.customize.size])
        + str(Config.customize.member_suffix).format(**apiParse)
    )
    return fullMessage


@memberImage.args_parser
@processSession(pluginName=MEMBER_IMAGE_METHOD)
@SyncToAsync
def _(session: CommandSession):
    strippedArgs = session.current_arg_text.strip()
    if not strippedArgs:
        session.pause("请输入画师的用户ID")
    numberArgs = extract_numbers(session.current_arg_text)
    if len(numberArgs) > 2:
        session.pause("您输入的参数不正确")
    page, member = numberArgs if len(numberArgs) == 2 else (1, numberArgs[0])
    session.state["page"], session.state["id"] = int(page), int(member)


@on_command(RANK_IMAGE_METHOD, aliases=("一图",))
@processSession(pluginName=RANK_IMAGE_METHOD)
@SyncToAsync
def _(session: CommandSession):
    global _RANK_CACHE
    session.send("开始获取一图")
    randomRank = random.choice(["day", "week", "month"])
    apiParse = parseMultiImage(pixiv.getRank(randomRank))
    if apiParse["result"]:
        cache.update(randomRank, apiParse)
    else:
        apiParse = cache.get(randomRank)
    choiceResult = random.choice(
        [data for data in apiParse["result"] if data["type"] == "illust"]
    )
    imageLinks = [i["large"] for i in choiceResult["download"]][: Config.customize.size]
    images = downloadMutliImage(imageLinks)
    messageRepeat = [str(MessageSegment.image(images[i])) for i in imageLinks]
    fullMessage = (
        str(Config.customize.rank_prefix).format(**choiceResult)
        + "\n".join(messageRepeat)
        + "\n"
        + str(Config.customize.rank_suffix).format(**choiceResult)
    )
    return fullMessage


@on_command(
    f"{OPERATING_METHOD}_enable", aliases=("打开R18", "启用R18"), permission=POWER_GROUP
)
@processSession(pluginName=OPERATING_METHOD)
@SyncToAsync
def enableR18(session: CommandSession):
    key = session.get("key")
    settings = PluginManager.settings(OPERATING_METHOD, ctx=session.ctx)
    if str(settings.settings.get("key", "")).upper() != str(key).upper():
        session.finish(f"密钥{key}无法激活该功能")
    PluginManager.settings(MEMBER_IMAGE_METHOD, ctx=session.ctx).settings = {
        "r-18": True
    }
    PluginManager.settings(SEARCH_IMAGE_METHOD, ctx=session.ctx).settings = {
        "r-18": True
    }
    PluginManager.settings(GET_IMAGE_METHOD, ctx=session.ctx).settings = {"r-18": True}
    return "封印已成功解除", False


@enableR18.args_parser
@processSession(pluginName=OPERATING_METHOD)
@SyncToAsync
def _(session: CommandSession):
    from re import search

    strippedArgs = session.current_arg_text.strip()
    matchObj = search(r"[a-fA-F0-9]{8,40}", strippedArgs)
    if not matchObj:
        session.pause("请输入激活密钥")
    session.state["key"] = str(matchObj.group(0)).upper()


@on_command(
    f"{OPERATING_METHOD}_disable", aliases=("禁用R18", "关闭R18"), permission=POWER_GROUP
)
@processSession(pluginName=OPERATING_METHOD)
@SyncToAsync
def disableR18(session: CommandSession):
    PluginManager.settings(MEMBER_IMAGE_METHOD, ctx=session.ctx).settings = {
        "r-18": False
    }
    PluginManager.settings(SEARCH_IMAGE_METHOD, ctx=session.ctx).settings = {
        "r-18": False
    }
    PluginManager.settings(GET_IMAGE_METHOD, ctx=session.ctx).settings = {"r-18": False}
    return "强大的力量已被封印", False


@on_command(f"{OPERATING_METHOD}_key", aliases=("生成R18密钥",), permission=SUPERUSER)
@processSession(pluginName=OPERATING_METHOD)
@SyncToAsync
def r18KeyGen(session: CommandSession):
    key = token_hex(8).upper()
    PluginManager.settings(OPERATING_METHOD, ctx=session.ctx).settings = {"key": key}
    return f"密钥生成完毕,为{key}"


@on_command(f"{OPERATING_METHOD}_back", aliases=("收回R18密钥",), permission=SUPERUSER)
@processSession(pluginName=OPERATING_METHOD)
@SyncToAsync
def r18KeyBack(session: CommandSession):
    oldKey = PluginManager.settings(OPERATING_METHOD, ctx=session.ctx).settings.get(
        "key", token_hex(8)
    )
    key = "".join([chr(ord(i) + 10) for i in list(oldKey)])
    PluginManager.settings(OPERATING_METHOD, ctx=session.ctx).settings = {"key": key}
    return "分发的密钥已被收回"
