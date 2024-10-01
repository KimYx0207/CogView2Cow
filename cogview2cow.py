import re
import requests
import json
import os
import threading
import time
from io import BytesIO
import plugins
from plugins import *
from bridge.context import ContextType, Context
from bridge.reply import Reply, ReplyType
from common.log import logger
from channel.wechat.wechat_channel import WechatChannel

@plugins.register(name="cogview2cow",
                  desc="CogView画图插件",
                  version="1.0",
                  author="KimYx 微信：xun900207（备注AI）",
                  desire_priority=100)
class CogView2Cow(Plugin):
    # 更新后的 RATIO_MAP
    RATIO_MAP = {
        "1:1": "1024x1024",
        "1:2": "720x1440",
        "2:1": "1440x720",
        "3:4": "864x1152",
        "4:3": "1152x864",
        "9:16": "768x1344",
        "16:9": "1344x768"
    }

    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        self.task_ids = {}  # 用于存储每个用户的任务ID
        self.config_data = None
        self.video_tasks = {}  # 存储未完成的任务
        if self.load_config():
            self.start_cleanup_scheduler()
        logger.info(f"[{__class__.__name__}] 初始化完成")

    def load_config(self):
        if self.config_data:
            return True  # 配置已加载

        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as file:
                self.config_data = json.load(file)
                # 检查并创建存储目录
                storage_path = self.config_data.get('storage_path', './')
                if not os.path.exists(storage_path):
                    os.makedirs(storage_path)
                    logger.info(f"创建存储目录: {storage_path}")
            # 提取触发词
            self.image_command = self.config_data.get('image_command', '智谱画图')
            self.video_command = self.config_data.get('video_command', '智谱视频')
            self.query_command = self.config_data.get('query_command', '查询进度')
        else:
            logger.error(f"请先配置 {config_path} 文件")
            return False
        return True

    def get_help_text(self, **kwargs):
        help_text = (
            "插件使用指南：\n"
            f"1. **生成图片**：输入 \"{self.image_command} [描述]\"，例如：\n"
            f"   - `{self.image_command} 一只可爱的猫`\n"
            "   - 您可以使用 `--ar 宽高比` 来指定图片比例，支持的比例有：\n"
            "     `1:1`、`1:2`、`2:1`、`3:4`、`4:3`、`16:9`、`9:16`。\n"
            f"   - 示例：`{self.image_command} 美丽的风景 --ar 16:9`\n"
            f"2. **生成视频**：输入 \"{self.video_command} [描述]\"，例如：\n"
            f"   - `{self.video_command} 一个在公园里奔跑的女孩`\n"
            f"3. **查询视频进度**：输入 \"{self.query_command}\"，将查询您的任务状态。\n"
        )
        return help_text

    def on_handle_context(self, e_context: EventContext):
        if e_context['context'].type != ContextType.TEXT:
            return
        self.content = e_context["context"].content.strip()
        user_id = e_context['context']['session_id']  # 获取用户ID
        isgroup = e_context['context']['isgroup']  # 获取是否是群聊

        if self.content.startswith(self.image_command):
            logger.info(f"[{__class__.__name__}] 收到消息: {self.content}")
            self.handle_generation(e_context, user_id, isgroup, is_video=False)
        elif self.content.startswith(self.video_command):
            logger.info(f"[{__class__.__name__}] 收到视频生成请求: {self.content}")
            self.handle_generation(e_context, user_id, isgroup, is_video=True)
        elif self.content.startswith(self.query_command):
            logger.info(f"[{__class__.__name__}] 收到进度查询请求: {self.content}")
            self.handle_query(e_context, user_id)
        else:
            return  # 不处理其他消息

    def handle_generation(self, e_context, user_id, isgroup, is_video):
        if not self.load_config():
            return

        if is_video:
            result, translated_prompt = self.cogview_video(user_id)
        else:
            result, translated_prompt = self.cogview2cow()

        if result is not None:
            # 在回复中包含翻译后的提示词
            reply_text = f"任务已提交。\n翻译后的提示词：{translated_prompt}"
            self.send_text_message(e_context['context'], reply_text)
            if is_video:
                # 存储任务信息，包括上下文
                task_id = result['id']
                self.video_tasks[task_id] = {
                    'user_id': user_id,
                    'isgroup': isgroup,
                    'context': e_context['context'],
                    'status': 'PROCESSING',
                    'start_time': time.time()
                }
                # 启动线程下载和发送视频
                threading.Thread(target=self.download_and_send_video, args=(result, task_id), daemon=True).start()
                e_context.action = EventAction.BREAK_PASS
            else:
                reply = Reply()
                reply.type = ReplyType.IMAGE
                reply.content = result  # 返回图片文件路径
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
        else:
            reply = Reply()
            reply.type = ReplyType.ERROR
            reply.content = "生成失败，请稍后重试。"
            e_context["reply"] = reply
            e_context.action = EventAction.BREAK_PASS

    def handle_query(self, e_context, user_id):
        # 您可以实现查询逻辑，例如查询用户的任务状态
        reply = Reply()
        reply.type = ReplyType.TEXT
        reply.content = "查询功能尚未实现。"
        e_context["reply"] = reply
        e_context.action = EventAction.BREAK_PASS

    def translate_prompt(self, prompt):
        if not self.load_config():
            return prompt

        translate_api_url = self.config_data.get('translate_api_url', '')
        translate_api_key = self.config_data.get('translate_api_key', '')
        translate_model = self.config_data.get('translate_model', '')

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {translate_api_key}"
        }

        # 构建请求的 payload
        payload = {
            "model": translate_model,
            "messages": [
                {"role": "system", "content": "请将以下内容翻译成英文："},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 1000
        }

        try:
            response = requests.post(translate_api_url, json=payload, headers=headers)
            response.raise_for_status()
            response_data = response.json()
            translated_prompt = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
            logger.info(f"翻译后的提示词: {translated_prompt}")
            return translated_prompt.strip()
        except Exception as e:
            logger.error(f"翻译接口抛出异常: {e}")
            return prompt

    def extract_image_size(self, prompt: str) -> (str, str):
        match = re.search(r'--ar (\d+:\d+)', prompt)
        if match:
            ratio = match.group(1).strip()
            size = self.RATIO_MAP.get(ratio, "1024x1024")
            prompt = re.sub(r'--ar \d+:\d+', '', prompt).strip()
        else:
            size = "1024x1024"
        logger.debug(f"[{__class__.__name__}] 提取的图片尺寸: {size}")
        return size, prompt

    def cogview2cow(self):
        if not self.load_config():
            return None, None

        key = self.config_data.get('cogview_api_key', '')
        image_base_url = self.config_data.get('image_base_url', '')
        image_model = self.config_data.get('image_model', '')
        storage_path = self.config_data.get('storage_path', './')

        logger.info("使用密钥: " + key)

        try:
            # 去掉触发词前缀
            prompt = self.content[len(self.image_command):].strip()
            # 提取图片尺寸
            size, prompt = self.extract_image_size(prompt)
            # 翻译提示词
            translated_prompt = self.translate_prompt(prompt)
            if not translated_prompt:
                return None, None

            payload = {
                "model": image_model,
                "prompt": translated_prompt,
            }
            # 只有 cogview-3-plus 支持 size 参数
            if image_model == "cogview-3-plus" and size:
                payload["size"] = size
            headers = {
                "accept": "application/json",
                "content-type": "application/json",
                "authorization": "Bearer " + key
            }

            response = requests.post(image_base_url, json=payload, headers=headers)
            response.raise_for_status()
            response_data = response.json()
            logger.info(response_data)

            img_url = response_data['data'][0]['url']
            logger.info("生成的图片URL: " + img_url)

            # 下载图片
            img_data = requests.get(img_url).content
            timestamp = int(time.time())
            img_filename = f"image_{timestamp}.png"
            img_path = os.path.join(storage_path, img_filename)
            with open(img_path, 'wb') as handler:
                handler.write(img_data)
            logger.info(f"图片已保存到: {img_path}")
            return img_path, translated_prompt  # 返回图片的文件路径和翻译后的提示词
        except Exception as e:
            logger.error(f"接口抛出异常: {e}")
            return None, None

    def cogview_video(self, user_id):
        if not self.load_config():
            return None, None

        key = self.config_data.get('cogview_api_key', '')
        video_base_url = self.config_data.get('video_base_url', '')
        video_model = self.config_data.get('video_model', '')

        logger.info("使用密钥: " + key)

        try:
            # 去掉触发词前缀
            prompt = self.content[len(self.video_command):].strip()
            # 翻译提示词
            translated_prompt = self.translate_prompt(prompt)
            if not translated_prompt:
                return None, None

            payload = {
                "model": video_model,
                "prompt": translated_prompt,
                "user_id": user_id  # 传入用户ID
            }
            headers = {
                "accept": "application/json",
                "content-type": "application/json",
                "authorization": "Bearer " + key
            }

            response = requests.post(video_base_url, json=payload, headers=headers)
            response.raise_for_status()
            response_data = response.json()
            logger.info(response_data)

            if 'id' in response_data:
                return response_data, translated_prompt  # 返回响应和翻译后的提示词
            else:
                logger.error("API 响应不包含 id: " + str(response_data))
                return None, None
        except Exception as e:
            logger.error(f"接口抛出异常: {e}")
            return None, None



