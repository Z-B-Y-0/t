from threading import Thread
import subprocess
from flask import Flask, render_template_string, request, redirect, url_for, abort, send_file
import urllib.parse
import requests
from moviepy.editor import VideoFileClip
import os
import shutil
from itertools import zip_longest
from tqdm import tqdm
from datetime import datetime
import json



app = Flask(__name__)

# 获取B站视频信息的函数
def get_video_info(bid):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1 Edg/124.0.0.0',
            'bvid': bid
        }
        video_info_url = 'https://api.bilibili.com/x/web-interface/view?bvid=' + headers['bvid']
        response = requests.get(video_info_url, headers=headers).json()["data"]
        return response
    except requests.RequestException as e:
        return None

# 下载并转换视频的函数
def download_and_convert(video_info, cookie, video_id):
    try:
        cid = video_info["cid"]
        bvid = video_info["bvid"]
        avid = video_info["aid"]
        title = video_info["title"]

        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1 Edg/124.0.0.0',
            'Referer': 'https://www.bilibili.com/' + bvid,
            'Cookie': cookie
        }
        video_url = f'https://api.bilibili.com/x/player/wbi/playurl?fnval=4048&qn=120&avid={avid}&bvid={bvid}&cid={cid}'
        response = requests.get(video_url, headers=headers).json()["data"]
        #print(response)
        high_video_id = int(response["dash"]["video"][0]["id"])
        high_video_quality = response["accept_description"][response["accept_quality"].index(high_video_id)]

        video_quality = response["accept_description"][response["accept_quality"].index(int(video_id))]
        download_video_url = next(video["baseUrl"] for video in response["dash"]["video"] if video["id"] == int(video_id))

        if download_video_url:
            os.makedirs('m4s', exist_ok=True)
            download_file = os.path.join('m4s', title + '- ' + video_quality + '.m4s')

            try:
                response = requests.get(download_video_url, headers=headers, stream=True)
                response.raise_for_status()

                total_size = int(response.headers.get('content-length', 0))

                with open(download_file, 'wb') as f:
                    with tqdm(total=total_size, unit='B', unit_scale=True, unit_divisor=1024, desc="下载进度") as pbar:
                        for data in response.iter_content(chunk_size=1024):
                            f.write(data)
                            pbar.update(len(data))

                input_file = download_file
                output_file = os.path.join('mp4', title + '- ' + video_quality + '.mp4')
                os.makedirs('mp4', exist_ok=True)
                clip = VideoFileClip(input_file)
                clip.write_videofile(output_file)

                os.remove(download_file)
                shutil.rmtree('m4s')
                #<a href="/">返回首页</a>
                return f'''
                <p>视频导出完成：<a href="/file/{title + '- ' + video_quality}.mp4">http://127.0.0.1:1145/file/{title + '- ' + video_quality}.mp4</a>
                '''


            except requests.exceptions.RequestException as e:
                return f"下载失败: {e}"
        else:
            return "下载失败，未找到视频URL"
    except Exception as e:
        return f"发生错误：{e}"

@app.route('/')
def home():
    return render_template_string('''
        <!DOCTYPE html>
        <html lang="zh">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>欢迎使用Bilibili视频下载器</title>
        </head>
        <body>
            <h1>欢迎使用Bilibili视频下载器</h1>
            <form action="{{ url_for('get_cookie') }}" method="post">
                <label for="cookie">请输入Cookie:</label>
                <input type="text" id="cookie" name="cookie">
                <button type="submit">下一步</button>
            </form>
        </body>
        </html>
    ''')

@app.route('/get_cookie', methods=['POST'])
def get_cookie():
    cookie = request.form.get('cookie')
    if(cookie):
        return redirect(url_for('get_url', cookie=cookie))
    else:
        cookie = "buvid3=114514"
        return redirect(url_for('get_url', cookie=cookie))

@app.route('/get_url')
def get_url():
    cookie = request.args.get('cookie')
    return render_template_string('''
        <!DOCTYPE html>
        <html lang="zh">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>输入B站链接</title>
        </head>
        <body>
            <h1>输入B站链接</h1>
            <form action="{{ url_for('select_video') }}" method="post">
                <input type="hidden" name="cookie" value="{{ cookie }}">
                <label for="bili_url">B站链接:</label>
                <input type="text" id="bili_url" name="bili_url">
                <button type="submit">下一步</button>
            </form>
        </body>
        </html>
    ''', cookie=request.args.get('cookie'))

@app.route('/select_video', methods=['POST'])
def select_video():
    cookie = request.form.get('cookie')
    bili_url = request.form.get('bili_url')

    try:
        # 提取 bili_bid
        bili_url_parts = bili_url.split('?')[0].split('/')
        bili_bid = bili_url_parts[-1] if bili_url_parts[-1] != '' else bili_url_parts[-2]

        # 获取视频信息
        video_info = get_video_info(bili_bid)
        if not video_info:
            return "未能获取视频信息，请检查输入的链接或网络连接。"

        # 请求视频播放URL
        response = requests.get(
            f'https://api.bilibili.com/x/player/wbi/playurl?fnval=4048&qn=120&avid={video_info["aid"]}&bvid={video_info["bvid"]}&cid={video_info["cid"]}',
            headers={
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1 Edg/124.0.0.0',
                'Referer': 'https://www.bilibili.com/' + video_info["bvid"],
                'Cookie': cookie
            }
        ).json()

        if "data" not in response:
            return "未能获取视频数据，请检查视频信息或网络连接。"

        data = response["data"]

        high_video_id = int(data["dash"]["video"][0]["id"])
        high_video_quality = data["accept_description"][data["accept_quality"].index(high_video_id)]

        # 生成清晰度列表
        video_quality_list = list(zip_longest(data["accept_description"], data["accept_quality"], fillvalue="无"))

        # 将视频链接添加到 video_info
        video_info['url'] = "https://www.bilibili.com/" + video_info['bvid']

        return render_template_string('''
            <!DOCTYPE html>
            <html lang="zh">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>选择视频清晰度</title>
            </head>
            <body>
                <h1>选择视频清晰度</h1>
                <form action="{{ url_for('confirm_download') }}" method="post">
                    <input type="hidden" name="cookie" value="{{ cookie }}">

                    <label for="video_id">视频: {{ title }}</label>
                    <br>
                    <label for="video_id">视频链接: <a href="{{ video_info['url'] }}" target="_blank">{{ video_info['url'] }}</a></label>
                    <br>                  
                    <label for="video_id">所有清晰度:</label>
                    <ul>
                        {% for description, quality in video_quality_list %}
                        <li>{{ description }} (id: {{ quality }})</li>
                        {% endfor %}
                    </ul>
                    <br>
                    <label for="video_id">请输入清晰度ID (默认最高: {{ high_video_quality }}):</label>                
                    <input type="text" id="video_id" name="video_id" value="{{ high_video_id }}">
                    <input type="hidden" id="video_info" name="video_info" value="{{ video_info['bvid'] }}">
                    <button type="submit">确定</button>
                </form>
            </body>
            </html>
        ''', cookie=cookie, video_info=video_info, video_quality_list=video_quality_list,
           high_video_id=high_video_id, high_video_quality=high_video_quality,
           title=video_info["owner"]["name"] + ' - ' + video_info["title"])
    except requests.RequestException as e:
        return f"网络请求错误: {e}"
    except KeyError as e:
        return f"数据格式错误: 缺少键 {e}"
    except json.JSONDecodeError as e:
        return f"JSON解析错误: {e}"
    except Exception as e:
        return f"发生错误：{e}"


@app.route('/confirm_download', methods=['POST'])
def confirm_download():

    #print("请求表单数据:", request.form)  # 打印表单数据以进行调试
    try:
        video_info = request.form.get('video_info')
        if not video_info:
            return "错误: 未提供 video_info 数据"
        else:
            bvid = video_info
        '''
        video_info = json.loads(video_info_str)
        print("解析后的 video_info:", video_info)  # 打印解析后的数据

        if not isinstance(video_info, dict):
            return "错误: video_info 数据格式不正确"


        bvid = video_info.get('bvid')
        if not bvid:
            return "错误: video_info 数据缺少 bvid 字段"
        '''    

        video_info_data = get_video_info(bvid)
        if not video_info_data:
            return "错误: 无法获取视频信息"

        video_id = request.form.get('video_id')

        result = download_and_convert(video_info_data, request.form.get('cookie'), video_id)

        return f'''
            <!DOCTYPE html>
            <html lang="zh">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>下载完成</title>
            </head>
            <body>
                <h1>{result}</h1>
                <a href="/">返回首页</a>
            </body>
            </html>
        '''
    except json.JSONDecodeError as e:
        return f"JSON解析错误: {e}"
    except Exception as e:
        return f"发生错误: {e}"

@app.route('/file/<path:filename>', methods=['GET'])
def file(filename):
    # URL 解码文件名
    file_name = urllib.parse.unquote(filename)


    # 设定文件路径（文件存储在 mp4 文件夹中）
    file_path = os.path.join('mp4', file_name)
    print(f"Requested file: {file_path}")
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            #abort(404)  # 文件不存在，返回 404 错误
            return '''
            <meta http-equiv="refresh" content="0; URL=/file/video.mp4">
            '''

        # 发送文件
        return send_file(
            file_path,
            # 不设置 as_attachment=True，这样浏览器将尝试直接播放文件
            mimetype='video/mp4',
            # 可选: 设置 Content-Disposition 为 'inline' 以确保文件直接在浏览器中播放
            # download_name=file_name,  # 如果不需要重命名下载的文件，可以去掉
            as_attachment=False
        )
    except Exception as e:
        return f"发生错误：{e}", 500

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=1145, debug=True)

    server = Thread(target=run)
    server.start()
