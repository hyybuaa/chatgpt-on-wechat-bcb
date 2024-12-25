import requests

url = "http://1.92.69.23:12003/v1/chat/completions"
headers = {
    "Content-Type": "application/json",
    "API-Key": "sk-bcb_Crcg4k0vAhMkfJft0DOgCImyZ6mEzeOvJEBybZh42HjZdMLkijUhH4ObtQmQM9QE"
}
data = {'model': 'math-assistant', 'temperature': 0.7, 'top_p': 1.0, 'messages': [{'role': 'user', 'content': [{'type': 'text', 'text': '根据上下文解读图片内容'}, {'type': 'image_url', 'image_url': '/root/chatgpt-on-wechat-bcb/tmp/241225-203040.jpg'}]}]}
# data = {
#     "model": "math-assistant",
#     "messages": [
#         {
#             "role": "user",
#             "content": "你好，请帮我解答这个问题。"
#         }
#     ],
#     "stream": False,
#     "user": "user_123"
# }

response = requests.post(url, headers=headers, json=data)

print(response.status_code)
print(response.json())

# 