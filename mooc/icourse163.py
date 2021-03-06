# -*- coding: utf-8 -*-
"""中国大学MOOC"""

import time
import json
from .utils import *

CANDY = Crawler()
CONFIG = {}
FILES = {}


def get_summary(url):
    """从课程主页面获取信息"""

    url = url.replace('learn/', 'course/')
    res = CANDY.get(url).text

    term_id = re.search(r'termId : "(\d+)"', res).group(1)
    names = re.findall(r'name:"(.+)"', res)

    ids = re.findall(r'id : "(\d+)",\ncourse', res)
    #print(ids)

    dir_name = course_dir(*names[:2])

    print(dir_name)
    CONFIG['term_id'] = term_id
    return term_id, dir_name, ids


def parse_resource(resource):
    """解析资源地址和下载资源"""

    post_data = {'callCount': '1', 'scriptSessionId': '${scriptSessionId}190',
                 'httpSessionId': '5531d06316b34b9486a6891710115ebc', 'c0-scriptName': 'CourseBean',
                 'c0-methodName': 'getLessonUnitLearnVo', 'c0-id': '0', 'c0-param0': 'number:' + resource.meta[0],
                 'c0-param1': 'number:' + resource.meta[1], 'c0-param2': 'number:0',
                 'c0-param3': 'number:' + resource.meta[2], 'batchId': str(int(time.time()) * 1000)}
    res = CANDY.post('https://www.icourse163.org/dwr/call/plaincall/CourseBean.getLessonUnitLearnVo.dwr',
                     data=post_data).text

    file_name = resource.file_name
    if resource.type == 'Video':
        if CONFIG['hasToken']:
            video_token = CANDY.post('https://www.icourse163.org/web/j/resourceRpcBean.getVideoToken.rpc?csrfKey='+CONFIG['token'], data ={
                'videoId': resource.meta[0],
                'targetId': CONFIG['term_id'],
                'targetType': '0',
                }).json()['result']['signature']
            data = CANDY.post('https://vod.study.163.com/eds/api/v1/vod/video', data={
                'videoId': resource.meta[0],
                'signature': video_token,
                'clientType': '1'
            }).json()

            resolutions = [3, 2, 1]
            for sp in resolutions[CONFIG['resolution']:]:
                # TODO: 增加视频格式选择
                for video in data['result']['videos']:
                    if video['quality'] == sp and video['format'] == 'mp4':
                        url = video['videoUrl']
                        ext = '.mp4'
                        break
                else:
                    continue
                break
            res_print(file_name + ext)
            FILES['renamer'].write(re.search(r'(\w+\.mp4)', url).group(1), file_name, ext)
            FILES['video'].write_string(url)
            resource.ext = ext

        else:
            resolutions = ['Shd', 'Hd', 'Sd']
            for sp in resolutions[CONFIG['resolution']:]:
                # TODO: 增加视频格式选择
                # video_info = re.search(r'%sUrl="(?P<url>.*?(?P<ext>\.((m3u8)|(mp4)|(flv))).*?)"' % sp, res)
                video_info = re.search(r'(?P<ext>mp4)%sUrl="(?P<url>.*?\.(?P=ext).*?)"' % sp, res)
                if video_info:
                    url, ext = video_info.group('url', 'ext')
                    ext = '.' + ext
                    break
            res_print(file_name + ext)
            FILES['renamer'].write(re.search(r'(\w+\.((m3u8)|(mp4)|(flv)))', url).group(1), file_name, ext)
            FILES['video'].write_string(url)
            resource.ext = ext

        if not CONFIG['sub']:
            return
        subtitles = re.findall(r'name="(.+)";.*url="(.*?)"', res)
        WORK_DIR.change('Videos')
        for subtitle in subtitles:
            if len(subtitles) == 1:
                sub_name = file_name + '.srt'
            else:
                subtitle_lang = subtitle[0].encode('utf_8').decode('unicode_escape')
                sub_name = file_name + '_' + subtitle_lang + '.srt'
            res_print(sub_name)
            CANDY.download_bin(subtitle[1], WORK_DIR.file(sub_name))

    elif resource.type == 'Document':
        if WORK_DIR.exist(file_name + '.pdf'):
            return
        pdf_url = re.search(r'textOrigUrl:"(.*?)"', res).group(1)
        res_print(file_name + '.pdf')
        CANDY.download_bin(pdf_url, WORK_DIR.file(file_name + '.pdf'))

    elif resource.type == 'Rich':
        if WORK_DIR.exist(file_name + '.html'):
            return
        text = re.search(r'htmlContent:"(.*)",id', res.encode('utf_8').decode('unicode_escape'), re.S).group(1)
        res_print(file_name + '.html')
        with open(WORK_DIR.file(file_name + '.html'), 'w', encoding='utf_8') as file:
            file.write(text)


def get_resource(term_id):
    """获取各种资源"""

    outline = Outline()
    counter = Counter()

    video_list = []
    pdf_list = []
    rich_text_list = []

    post_data = {'callCount': '1', 'scriptSessionId': '${scriptSessionId}190', 'c0-scriptName': 'CourseBean',
                 'c0-methodName': 'getMocTermDto', 'c0-id': '0', 'c0-param0': 'number:' + term_id,
                 'c0-param1': 'number:0', 'c0-param2': 'boolean:true', 'batchId': str(int(time.time()) * 1000)}
    res = CANDY.post('https://www.icourse163.org/dwr/call/plaincall/CourseBean.getMocTermDto.dwr',
                     data=post_data).text.encode('utf_8').decode('unicode_escape')
    
    chapters = re.findall(r'homeworks=\w+;.+id=(\d+).+name="([\s\S]+?)";', res)
    for chapter in chapters:
        counter.add(0)
        outline.write(chapter[1], counter, 0)

        lessons = re.findall(r'chapterId=' + chapter[0] + r'.+contentId=null.+contentType=1.+id=(\d+).+name="([\s\S]+?)"', res)
        for lesson in lessons:
            counter.add(1)
            outline.write(lesson[1], counter, 1)

            videos = re.findall(r'contentId=(\d+).+contentType=(1).+id=(\d+).+lessonId=' +
                                lesson[0] + r'.+name="([\s\S]+?)"', res)
            for video in videos:
                counter.add(2)
                outline.write(video[3], counter, 2, sign='#')
                video_list.append(Video(counter, video[3], video))
            counter.reset()

            pdfs = re.findall(r'contentId=(\d+).+contentType=(3).+id=(\d+).+lessonId=' +
                              lesson[0] + r'.+name="([\s\S]+?)"', res)
            for pdf in pdfs:
                counter.add(2)
                outline.write(pdf[3], counter, 2, sign='*')
                if CONFIG['doc']:
                    pdf_list.append(Document(counter, pdf[3], pdf))
            counter.reset()

            rich_text = re.findall(r'contentId=(\d+).+contentType=(4).+id=(\d+).+jsonContent=(.+?);.+lessonId=' +
                                   lesson[0] + r'.+name="([\s\S]]+?)"', res)
            for text in rich_text:
                counter.add(2)
                outline.write(text[4], counter, 2, sign='+')
                if CONFIG['text']:
                    rich_text_list.append(RichText(counter, text[4], text))
                if CONFIG['file']:
                    if text[3] != 'null' and text[3] != '""':
                        params = {'nosKey': re.search('nosKey":"(.+?)"', text[3]).group(1),
                                  'fileName': re.search('"fileName":"(.+?)"', text[3]).group(1)}
                        file_name = Resource.file_to_save(params['fileName'])
                        outline.write(file_name, counter, 2, sign='!')

                        WORK_DIR.change('Files')
                        res_print(params['fileName'])
                        file_name = '%s %s' % (counter, file_name)
                        CANDY.download_bin('https://www.icourse163.org/course/attachment.htm',
                                           WORK_DIR.file(file_name), params=params)
            counter.reset()
    
    if video_list:
        rename = WORK_DIR.file('Names.txt') if CONFIG['rename'] else False
        WORK_DIR.change('Videos')
        if CONFIG['dpl']:
            playlist = Playlist()
            parse_res_list(video_list, rename, parse_resource, playlist.write)
        else:
            parse_res_list(video_list, rename, parse_resource)
    if pdf_list:
        WORK_DIR.change('PDFs')
        parse_res_list(pdf_list, None, parse_resource)
    if rich_text_list:
        WORK_DIR.change('Texts')
        parse_res_list(rich_text_list, None, parse_resource)

def get_discussion(ids, save_path):
    """获取讨论区内容"""
    questions = []
    question = []
    for term_id in ids:
        start = 1
        while len(question) or start==1:
            post_data = {'callCount': '1', 
                    'scriptSessionId': '${scriptSessionId}190',
                    'c0-scriptName': 'PostBean',
                    'c0-methodName': 'getAllPostsPagination',
                    'c0-id': '0',
                    'c0-param0': 'number:' + term_id,
                    'c0-param1': 'string:',
                    'c0-param2': 'number:1',
                    'c0-param3': 'string:' + str(start),
                    'c0-param4': 'number:20',
                    'c0-param5': 'boolean:false',
                    'c0-param6': 'null:null',
                    'batchId': str(int(time.time()) * 1000)}
            res = CANDY.post('https://www.icourse163.org/dwr/call/plaincall/PostBean.getAllPostsPagination.dwr',
                        data=post_data).text.encode('utf_8').decode('unicode_escape')

            question =  re.findall(r'id=(\d+).+title="([\s\S]+?)"?;', res)
            questions += question
            start+=1

    content_data = {'callCount': '1', 
             'scriptSessionId': '${scriptSessionId}190',
             'c0-scriptName': 'PostBean',
             'c0-methodName': 'getPaginationReplys',
             'c0-id': '0',
             'c0-param0': '',
             'c0-param1': 'number:2',
             'c0-param2': 'number:1',
             'batchId': str(int(time.time()) * 1000)}

    discription_data = {'callCount': '1', 
             'scriptSessionId': '${scriptSessionId}190',
             'c0-scriptName': 'PostBean',
             'c0-methodName': 'getPostDetailById',
             'c0-id': '0',
             'c0-param0': '',
             'batchId': str(int(time.time()) * 1000)}
    #print(questions)
    save_discussion_list = []
    for questionId in questions:
        print("====>拉取问题 %s" % questionId[1])
        content_data['c0-param0'] = "number:"+questionId[0]
        discription_data['c0-param0'] = "number:"+questionId[0]

        resData = CANDY.post('https://www.icourse163.org/dwr/call/plaincall/PostBean.getPaginationReplys.dwr',
                 data=content_data).text.encode('utf_8').decode('unicode_escape')

        #每个问题的回答
        answers = re.findall(r'content="([\s\S]+?)";.[\s\S]+?nickName="([\s\S]+?)";', resData)
        
        #具体问题内容
        resDiscription = CANDY.post('https://www.icourse163.org/dwr/call/plaincall/PostBean.getPostDetailById.dwr',
                    data=discription_data).text.encode('utf_8').decode('unicode_escape')

        questionContent = re.findall(r'content:"([\s\S]+?)",', resDiscription)[0]
        questionTitle = questionId[1]

        #转化为dict
        save_dict = {"question": questionTitle,
                    "questionContent":questionContent, 
                    "answers":answers}
        save_discussion_list.append(save_dict)

    with open(save_path,"w",encoding="utf-8") as f:
        json.dump(save_discussion_list,f,ensure_ascii=False)
        




def start(url, config, cookies):
    """调用接口函数"""

    global WORK_DIR
    CANDY.set_cookies(cookies)
    CONFIG.update(config)

    if cookies.get('NTESSTUDYSI'):
        CONFIG['hasToken'] = True
        CONFIG['token'] = cookies.get('NTESSTUDYSI')
    else:
        CONFIG['hasToken'] = False

    #输出配置
    print(CONFIG)

    term_id, dir_name, ids = get_summary(url)
    print("term id: " + str(term_id))
    WORK_DIR = WorkingDir(CONFIG['dir'], dir_name)
    FILES['discussion'] = WORK_DIR.file('discussion.json')
    WORK_DIR.change('Videos')
    FILES['renamer'] = Renamer(WORK_DIR.file('Rename.{ext}'))
    FILES['video'] = ClassicFile(WORK_DIR.file('Videos.txt'))

    get_resource(term_id)

    if CONFIG['discussion']:
        # 拉取讨论区
        print("====>开始拉取讨论区")
        get_discussion(ids, FILES['discussion'])


    if CONFIG['aria2']:
        for file in list(FILES.keys()):
            del FILES[file]
        WORK_DIR.change('Videos')
        aria2_download(CONFIG['aria2'], WORK_DIR.path, webui=CONFIG['aria2-webui'], session=CONFIG['aria2-session'])

