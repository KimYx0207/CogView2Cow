## 插件说明
基于智谱提供的AI绘画及视频功能。
地址: [[https://open.bigmodel.cn/usercenter/apikeys](https://open.bigmodel.cn/usercenter/apikeys)]，注册有2000次免费生图或视频机会。

## 插件安装

私聊微信机器人进行。
```
#installp https://github.com/KimYx0207/CogView2Cow.git
#scanp

```


## 插件配置
配置目录下的 `config.json`。

```
{
    "cogview_api_key": "your_cogview_api_key",                                    #智谱API KEY
    "image_base_url": "https://open.bigmodel.cn/api/paas/v4/images/generations",  #不用改
    "video_base_url": "https://open.bigmodel.cn/api/paas/v4/videos/generations",  #不用改
    "video_result_url": "https://open.bigmodel.cn/api/paas/v4/async-result/{id}", #不用改
    "image_model": "cogview-3-plus",                                              #不用改
    "video_model": "cogvideox",                                                   #不用改
    "translate_api_url": "https://api.siliconflow.cn/v1/chat/completions",        #使用LLM的交互地址
    "translate_api_key": "your_translate_api_key",                                #LLM的API KEY
    "ranslate_model": "Qwen/Qwen2.5-7B-Instruct",                                 #LLM使用的模型
    "storage_path": "/root/chatgpt-on-wechat/plugins/CogView2Cow/image_video",    #存储路径
    "cleanup_days": 3,                                                            #不用改
    "cleanup_check_interval_minutes": 1440,                                       #不用改
    "image_command": "智谱画图",                                                   #触发画图
    "video_command": "智谱视频",                                                   #触发视频
    "query_command": "查询进度"                                                    #触发进度查询+使用时添加ID
}

**## 插件使用**

智谱画图 一个小姑娘 --ar 1：1

        "1:1": "1024x1024",
        "1:2": "720x1440",
        "2:1": "1440x720",
        "3:4": "864x1152",
        "4:3": "1152x864",
        "9:16": "768x1344",
        "16:9": "1344x768"

智谱视频 一个小姑娘

```



![二维码基础款](https://github.com/KimYx0207/RaiseCard/assets/130755848/2a182d2c-8a43-4267-9e54-337dff85c5eb)
