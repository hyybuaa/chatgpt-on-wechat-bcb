# encoding:utf-8

import time
import os 

import openai
import openai.error
from bot.bot import Bot
from bot.session_manager import SessionManager
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from config import conf, load_config
from .moonshot_session import MoonshotSession
import requests


# ZhipuAI对话模型API
class MoonshotBot(Bot):
    def __init__(self):
        super().__init__()
        self.sessions = SessionManager(MoonshotSession, model=conf().get("model") or "moonshot-v1-128k")
        model = conf().get("model") or "moonshot-v1-128k"
        if model == "moonshot":
            model = "moonshot-v1-32k"
        self.args = {
            "model": model,  # 对话模型的名称
            "temperature": conf().get("temperature", 0.3),  # 如果设置，值域须为 [0, 1] 我们推荐 0.3，以达到较合适的效果。
            "top_p": conf().get("top_p", 1.0),  # 使用默认值
        }
        self.api_key = conf().get("moonshot_api_key")
        self.base_url = conf().get("moonshot_base_url", "https://api.moonshot.cn/v1/chat/completions")

    def reply(self, query, context=None):
        # acquire reply content
        if context.type == ContextType.TEXT:
            logger.info("[MOONSHOT_AI] query={}".format(query))

            session_id = context["session_id"]
            reply = None
            clear_memory_commands = conf().get("clear_memory_commands", ["#清除记忆"])
            if query in clear_memory_commands:
                self.sessions.clear_session(session_id)
                reply = Reply(ReplyType.INFO, "记忆已清除")
            elif query == "#清除所有":
                self.sessions.clear_all_session()
                reply = Reply(ReplyType.INFO, "所有人记忆已清除")
            elif query == "#更新配置":
                load_config()
                reply = Reply(ReplyType.INFO, "配置已更新")
            if reply:
                return reply
            session = self.sessions.session_query(query, session_id)
            logger.info("[MOONSHOT_AI] session query={}".format(session.messages))

            model = context.get("moonshot_model")
            new_args = self.args.copy()
            if model:
                new_args["model"] = model
            # if context.get('stream'):
            #     # reply in stream
            #     return self.reply_text_stream(query, new_query, session_id)

            reply_content = self.reply_text(session, args=new_args)
            logger.debug(
                "[MOONSHOT_AI] new_query={}, session_id={}, reply_cont={}, completion_tokens={}".format(
                    session.messages,
                    session_id,
                    reply_content["content"],
                    reply_content["completion_tokens"],
                )
            )
            if reply_content["completion_tokens"] == 0 and len(reply_content["content"]) > 0:
                reply = Reply(ReplyType.ERROR, reply_content["content"])
            elif reply_content["completion_tokens"] > 0:
                self.sessions.session_reply(reply_content["content"], session_id, reply_content["total_tokens"])
                reply = Reply(ReplyType.TEXT, reply_content["content"])
            else:
                reply = Reply(ReplyType.ERROR, reply_content["content"])
                logger.debug("[MOONSHOT_AI] reply {} used 0 tokens.".format(reply_content))
            return reply
        elif context.type == ContextType.IMAGE:
            logger.info("[MOONSHOT_AI] query={}".format(query))
            # 文件处理
            context.get("msg").prepare()
            file_path = context.content   
            os.system("mv {} {}".format(file_path, file_path.replace("png", "jpg")))
            context.content = file_path.replace("png", "jpg")
            os.system("chmod 755 {}".format(context.content))
            session_id = context["session_id"]
            reply = None
            clear_memory_commands = conf().get("clear_memory_commands", ["#清除记忆"])
            if query in clear_memory_commands:
                self.sessions.clear_session(session_id)
                reply = Reply(ReplyType.INFO, "记忆已清除")
            elif query == "#清除所有":
                self.sessions.clear_all_session()
                reply = Reply(ReplyType.INFO, "所有人记忆已清除")
            elif query == "#更新配置":
                load_config()
                reply = Reply(ReplyType.INFO, "配置已更新")
            if reply:
                return reply
            session = self.sessions.session_query(query, session_id)
            logger.info("[MOONSHOT_AI] session query={}".format(session.messages))

            model = context.get("moonshot_model")
            new_args = self.args.copy()
            if model:
                new_args["model"] = model
            # if context.get('stream'):
            #     # reply in stream
            #     return self.reply_text_stream(query, new_query, session_id)
            logger.info("开始reply_image...")
            reply_content = self.reply_image(session, args=new_args)
            logger.debug(
                "[MOONSHOT_AI] new_query={}, session_id={}, reply_cont={}, completion_tokens={}".format(
                    session.messages,
                    session_id,
                    reply_content["content"],
                    reply_content["completion_tokens"],
                )
            )
            if reply_content["completion_tokens"] == 0 and len(reply_content["content"]) > 0:
                reply = Reply(ReplyType.ERROR, reply_content["content"])
            elif reply_content["completion_tokens"] > 0:
                self.sessions.session_reply(reply_content["content"], session_id, reply_content["total_tokens"])
                reply = Reply(ReplyType.TEXT, reply_content["content"])
            else:
                reply = Reply(ReplyType.ERROR, reply_content["content"])
                logger.debug("[MOONSHOT_AI] reply {} used 0 tokens.".format(reply_content))
            logger.info("已经获取到图片")
            return reply
        else:
            reply = Reply(ReplyType.ERROR, "Bot不支持处理{}类型的消息".format(context.type))
            return reply

    def reply_text(self, session: MoonshotSession, args=None, retry_count=0) -> dict:
        """
        call openai's ChatCompletion to get the answer
        :param session: a conversation session
        :param session_id: session id
        :param retry_count: retry count
        :return: {}
        """
        try:
            headers = {
                "Content-Type": "application/json",
                "API-Key": self.api_key
            }
            body = args
            body["messages"] = session.messages[1:]
            logger.info("输入大模型的文本messages: {}".format(body["messages"]))
            # logger.debug("[MOONSHOT_AI] response={}".format(response))
            # logger.info("[MOONSHOT_AI] reply={}, total_tokens={}".format(response.choices[0]['message']['content'], response["usage"]["total_tokens"]))
            res = requests.post(
                self.base_url,
                headers=headers,
                json=body
            )
            logger.info("res: {}".format(res))
            if res.status_code == 200:
                response = res.json()
                return {
                    "total_tokens": response["usage"]["total_tokens"],
                    "completion_tokens": response["usage"]["completion_tokens"],
                    "content": response["choices"][0]["message"]["content"]
                }
            else:
                response = res.json()
                error = response.get("error")
                logger.error(f"[MOONSHOT_AI] chat failed, status_code={res.status_code}, "
                             f"msg={error.get('message')}, type={error.get('type')}")

                result = {"completion_tokens": 0, "content": "提问太快啦，请休息一下再问我吧"}
                need_retry = False
                if res.status_code >= 500:
                    # server error, need retry
                    logger.warn(f"[MOONSHOT_AI] do retry, times={retry_count}")
                    need_retry = retry_count < 2
                elif res.status_code == 401:
                    result["content"] = "授权失败，请检查API Key是否正确"
                elif res.status_code == 429:
                    result["content"] = "请求过于频繁，请稍后再试"
                    need_retry = retry_count < 2
                else:
                    need_retry = False

                if need_retry:
                    time.sleep(3)
                    return self.reply_text(session, args, retry_count + 1)
                else:
                    return result
        except Exception as e:
            logger.exception(e)
            need_retry = retry_count < 2
            result = {"completion_tokens": 0, "content": "我现在有点累了，等会再来吧"}
            if need_retry:
                return self.reply_text(session, args, retry_count + 1)
            else:
                return result
    
    def reply_image(self, session: MoonshotSession, args=None, retry_count=0) -> dict:
        """
        call openai's ChatCompletion to get the answer
        :param session: a conversation session
        :param session_id: session id
        :param retry_count: retry count
        :return: {}
        """
        try:
            headers = {
                "Content-Type": "application/json",
                "API-Key": self.api_key
            }
            body = args
            body["messages"] = self.multimodal_message(session.messages[1:])
            logger.info("输入大模型的多模态messages: {}".format(body["messages"]))
            logger.info("输入大模型的多模态body: {}".format(body))
            # logger.debug("[MOONSHOT_AI] response={}".format(response))
            # logger.info("[MOONSHOT_AI] reply={}, total_tokens={}".format(response.choices[0]['message']['content'], response["usage"]["total_tokens"]))
            res = requests.post(
                self.base_url,
                headers=headers,
                json=body
            )
            logger.info("res: {}".format(res))
            if res.status_code == 200:
                response = res.json()
                return {
                    "total_tokens": response["usage"]["total_tokens"],
                    "completion_tokens": response["usage"]["completion_tokens"],
                    "content": response["choices"][0]["message"]["content"]
                }
            else:
                response = res.json()
                error = response.get("error")
                logger.error(f"[MOONSHOT_AI] chat failed, status_code={res.status_code}, "
                             f"msg={error.get('message')}, type={error.get('type')}")

                result = {"completion_tokens": 0, "content": "提问太快啦，请休息一下再问我吧"}
                need_retry = False
                if res.status_code >= 500:
                    # server error, need retry
                    logger.warn(f"[MOONSHOT_AI] do retry, times={retry_count}")
                    need_retry = retry_count < 2
                elif res.status_code == 401:
                    result["content"] = "授权失败，请检查API Key是否正确"
                elif res.status_code == 429:
                    result["content"] = "请求过于频繁，请稍后再试"
                    need_retry = retry_count < 2
                else:
                    need_retry = False

                if need_retry:
                    time.sleep(3)
                    return self.reply_text(session, args, retry_count + 1)
                else:
                    return result
        except Exception as e:
            logger.exception(e)
            need_retry = retry_count < 2
            result = {"completion_tokens": 0, "content": "我现在有点累了，等会再来吧"}
            if need_retry:
                return self.reply_text(session, args, retry_count + 1)
            else:
                return result

    def multimodal_message(self, _messages):
        messages = []
        for item in _messages:
            if item['content'].endswith('.jpg') or item['content'].endswith('.png') or item['content'].endswith('.jpeg'):
                text_content = {"type": "text", "text": "请先在问题解答、课堂笔记辅导、知识点复习卡片、课后作业支持、错题练习5个任务上进行理解，并与用户的上下文结合，输出内容需以清晰、简洁、友好的形式呈现，并提供适当的背景知识补充或思路引导"}
                image_content = {"type": "image_url", "image_url": item['content'].replace(".png", ".jpg")}
                new_item = {'role': item['role'], 'content': [text_content, image_content]}
            else:
                content = {"type": "text", "text": item['content']}
                new_item = {'role': item['role'], 'content': [content]}
            messages.append(new_item)   
        return messages