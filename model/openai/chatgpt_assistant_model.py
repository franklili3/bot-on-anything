# encoding:utf-8

from model.model import Model
from config import model_conf, common_conf_val
from common import const
from common import log
import openai
import time

user_session = dict()

# OpenAI对话模型API (可用)
class ChatGPT_AssistantModel(Model):
    def __init__(self):
        openai.api_key = model_conf(const.OPEN_AI).get('api_key')
        api_base = model_conf(const.OPEN_AI).get('api_base')
        if api_base:
            openai.api_base = api_base
        proxy = model_conf(const.OPEN_AI).get('proxy')
        if proxy:
            openai.proxy = proxy
        log.info("[ChatGPT_Assistant] api_base={} proxy={}".format(
            api_base, proxy))
    def reply(self, query, context=None, retry_count=0):
        # acquire reply content
        if not context or not context.get('type') or context.get('type') == 'TEXT':
            #log.info("[ChatGPT_Assistant] query1={}".format(query))
            from_user_id = context['from_user_id']
            #log.info("[ChatGPT_Assistant] from_user_id={}".format(from_user_id))
            clear_memory_commands = common_conf_val('clear_memory_commands', ['#清除记忆'])
            if query in clear_memory_commands:
                Session.clear_session(from_user_id)
                return '记忆已清除'
            
        
            thread_id = Session.build_session_query(query, from_user_id)
            log.debug("[ChatGPT_Assistant] thread_id2={}".format(thread_id))

            # if context.get('stream'):
            #     # reply in stream
            #     return self.reply_text_stream(query, new_query, from_user_id)

            reply_content2 = self.reply_text(query, from_user_id, thread_id, 0)
            log.debug("[ChatGPT_Assistant] reply_content2={}".format(reply_content2))
            return reply_content2

        elif context.get('type', None) == 'IMAGE_CREATE':
            return self.create_img(query, 0)

    def reply_text(self, query, user_id, thread_id, retry_count=0):
        api_key = model_conf(const.OPEN_AI).get('api_key')
        #log.info("[ChatGPT_Assistant] api_key={}", api_key)
        #log.info("[ChatGPT_Assistant] query2={}".format(query))
        def wait_on_run(run, thread_id):
            while run.status == "queued" or run.status == "in_progress":
                run = client.beta.threads.runs.retrieve(
                    thread_id=thread_id,
                    run_id=run.id,
                )
                time.sleep(0.5)
            return run
        #log.info("[ChatGPT_Assistant] client has created")
        assistant_id = model_conf(const.OPEN_AI).get('assistant_id')
        #log.info("[ChatGPT_Assistant] assistant_id={}", assistant_id)            
        try:
            client = openai.OpenAI(api_key = api_key)
            #thread = client.beta.threads.create()
            #log.info("[ChatGPT_Assistant] thread.id={}", thread.id)
            #thread_id = Session.get_thread_id(user_id)

            message = client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=query
            )
            log.info("[ChatGPT_Assistant] message_id={}", message.id)

            run = client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=assistant_id,
                )
            log.info("[ChatGPT_Assistant] run.id={}", run.id)
            run = wait_on_run(run, thread_id)
            messages = client.beta.threads.messages.list(
                thread_id=thread_id
                )
            log.info("[ChatGPT_Assistant] messages_data[0]_id={}", messages.data[0].id)
            first_id = messages.first_id
            #log.info("[ChatGPT_Assistant] first_id={}", first_id)
            reply_content1 = ""
            for item in messages.data:
                if item.id == first_id and item.role == "assistant":
                    for content_item in item.content:
                        if content_item.type == "text":
                            reply_content1 += content_item.text.value
            log.info("[ChatGPT_Assistant] reply_content1={}", reply_content1)

            if reply_content1:
                # save conversation
                session = Session.save_session(query, reply_content1, user_id)
                log.info("[ChatGPT_Assistant] session3={}", session)
            return reply_content1
        except openai.error.RateLimitError as e:
            # rate limit exception
            log.warn(e)
            if retry_count < 1:
                time.sleep(5)
                log.warn("[ChatGPT_Assistant] RateLimit exceed, 第{}次重试".format(retry_count+1))
                return self.reply_text(query, user_id, retry_count+1)
            else:
                return "提问太快啦，请休息一下再问我吧"
        except openai.error.APIConnectionError as e:
            log.warn(e)
            log.warn("[ChatGPT_Assistant] APIConnection failed")
            return "我连接不到网络，请稍后重试"
        except openai.error.Timeout as e:
            log.warn(e)
            log.warn("[ChatGPT_Assistant] Timeout")
            return "我没有收到消息，请稍后重试"
        except Exception as e:
            # unknown exception
            log.exception(e)
            Session.clear_session(user_id)
            return "请再问我一次吧"


    async def reply_text_stream(self, query,  context, retry_count=0):
        try:
            user_id=context['from_user_id']
            new_query = Session.build_session_query(query, user_id)
            res = openai.ChatCompletion.create(
                model= model_conf(const.OPEN_AI).get("model") or "gpt-3.5-turbo",  # 对话模型的名称
                messages=new_query,
                temperature=model_conf(const.OPEN_AI).get("temperature", 0.75),  # 熵值，在[0,1]之间，越大表示选取的候选词越随机，回复越具有不确定性，建议和top_p参数二选一使用，创意性任务越大越好，精确性任务越小越好
                #max_tokens=4096,  # 回复最大的字符数，为输入和输出的总数
                #top_p=model_conf(const.OPEN_AI).get("top_p", 0.7),,  #候选词列表。0.7 意味着只考虑前70%候选词的标记，建议和temperature参数二选一使用
                frequency_penalty=model_conf(const.OPEN_AI).get("frequency_penalty", 0.0),  # [-2,2]之间，该值越大则越降低模型一行中的重复用词，更倾向于产生不同的内容
                presence_penalty=model_conf(const.OPEN_AI).get("presence_penalty", 1.0),  # [-2,2]之间，该值越大则越不受输入限制，将鼓励模型生成输入中不存在的新词，更倾向于产生不同的内容
                stream=True
            )
            full_response = ""
            for chunk in res:
                log.debug(chunk)
                if (chunk["choices"][0]["finish_reason"]=="stop"):
                    break
                chunk_message = chunk['choices'][0]['delta'].get("content")
                if(chunk_message):
                    full_response+=chunk_message
                yield False,full_response
            Session.save_session(query, full_response, user_id)
            log.info("[ChatGPT_Assistant]: reply={}", full_response)
            yield True,full_response

        except openai.error.RateLimitError as e:
            # rate limit exception
            log.warn(e)
            if retry_count < 1:
                time.sleep(5)
                log.warn("[ChatGPT_Assistant] RateLimit exceed, 第{}次重试".format(retry_count+1))
                yield True, self.reply_text_stream(query, user_id, retry_count+1)
            else:
                yield True, "提问太快啦，请休息一下再问我吧"
        except openai.error.APIConnectionError as e:
            log.warn(e)
            log.warn("[ChatGPT_Assistant] APIConnection failed")
            yield True, "我连接不到网络，请稍后重试"
        except openai.error.Timeout as e:
            log.warn(e)
            log.warn("[ChatGPT_Assistant] Timeout")
            yield True, "我没有收到消息，请稍后重试"
        except Exception as e:
            # unknown exception
            log.exception(e)
            Session.clear_session(user_id)
            yield True, "请再问我一次吧"

    def create_img(self, query, retry_count=0):
        try:
            log.info("[OPEN_AI] image_query={}".format(query))
            response = openai.Image.create(
                prompt=query,    #图片描述
                n=1,             #每次生成图片的数量
                size="256x256"   #图片大小,可选有 256x256, 512x512, 1024x1024
            )
            image_url = response['data'][0]['url']
            log.info("[OPEN_AI] image_url={}".format(image_url))
            return [image_url]
        except openai.error.RateLimitError as e:
            log.warn(e)
            if retry_count < 1:
                time.sleep(5)
                log.warn("[OPEN_AI] ImgCreate RateLimit exceed, 第{}次重试".format(retry_count+1))
                return self.reply_text(query, retry_count+1)
            else:
                return "提问太快啦，请休息一下再问我吧"
        except Exception as e:
            log.exception(e)
            return None


class Session(object):
    @staticmethod
    def build_session_query(query, user_id, retry_count=0):
        '''
        build query with conversation history
        e.g.  [
            {"thread_id": thread_id},
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Who won the world series in 2020?"},
            {"role": "assistant", "content": "The Los Angeles Dodgers won the World Series in 2020."},
            {"role": "user", "content": "Where was it played?"}
        ]
        :param query: query content
        :param user_id: from user id
        :return: thread_id
        '''
        session = user_session.get(user_id, [])
        if len(session) == 0:
            system_prompt = model_conf(const.OPEN_AI).get("character_desc", "")
            system_item = {'role': 'system', 'content': system_prompt}
            session.append(system_item)
            user_session[user_id] = session
            api_key = model_conf(const.OPEN_AI).get('api_key')
            try:
                client = openai.OpenAI(api_key = api_key)
                thread = client.beta.threads.create()
                thread_id = thread.id
                log.info("[ChatGPT_Assistant] thread_id1={}".format(thread_id))
                thread_id_item = {"thread_id": thread_id}
                session.append(thread_id_item)
                log.info("[ChatGPT_Assistant] session1={}".format(session))
            except openai.error.RateLimitError as e:
                # rate limit exception
                log.warn(e)
                if retry_count < 1:
                    time.sleep(5)
                    log.warn("[ChatGPT_Assistant] RateLimit exceed, 第{}次重试".format(retry_count+1))
                    return self.reply_text(query, user_id, retry_count+1)
                else:
                    return "提问太快啦，请休息一下再问我吧"
            except openai.error.APIConnectionError as e:
                log.warn(e)
                log.warn("[ChatGPT_Assistant] APIConnection failed")
                return "我连接不到网络，请稍后重试"
            except openai.error.Timeout as e:
                log.warn(e)
                log.warn("[ChatGPT_Assistant] Timeout")
                return "我没有收到消息，请稍后重试"
            except Exception as e:
                # unknown exception
                log.exception(e)
                Session.clear_session(user_id)
                return "请再问我一次吧"
        else:
            for dict in session:
                for key, value in dict.items():
                    if key == "thread_id":
                        thread_id = value
        user_item = {'role': 'user', 'content': query}
        session.append(user_item)
        log.info("[ChatGPT_Assistant] session2={}".format(session))
        return thread_id

    @staticmethod
    def save_session(query, answer, user_id, used_tokens=0):
        max_tokens = model_conf(const.OPEN_AI).get('conversation_max_tokens')
        max_history_num = model_conf(const.OPEN_AI).get('max_history_num', None)
        if not max_tokens or max_tokens > 4000:
            # default value
            max_tokens = 1000
        session = user_session.get(user_id)
        if session:
            # append conversation
            gpt_item = {'role': 'assistant', 'content': answer}
            session.append(gpt_item)

        if used_tokens > max_tokens and len(session) >= 3:
            # pop first conversation (TODO: more accurate calculation)
            session.pop(1)
            session.pop(1)

        if max_history_num is not None:
            while len(session) > max_history_num * 2 + 1:
                session.pop(1)
                session.pop(1)
        return session

    @staticmethod
    def clear_session(user_id):
        user_session[user_id] = []