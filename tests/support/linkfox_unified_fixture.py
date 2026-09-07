"""仅内存与仓库静态文件的 LinkFox 双节点 UI fixture，禁止真实生成。"""
import argparse
from http.server import ThreadingHTTPServer

import canvas_startup_fixture as fixture

MODELS = ['seedance2.0', 'seedance2.0fast', '可灵Omni', 'HappyHorse', '海螺2.3', 'wan2.6', '可灵2.6']
fixture.CONFIG['api_providers'].append({'id': 'linkfox', 'name': 'LinkFox', 'enabled': True,
                                      'video_models': MODELS, 'image_models': [], 'chat_models': []})


def project(canvas_id):
    return {'id': canvas_id, 'title': 'LinkFox双节点隔离验证', 'kind': 'classic', 'project': 'default',
        'updated_at': 1, 'viewport': {'x': 30, 'y': 40, 'scale': .85},
        'nodes': [
            {'id': 'video', 'type': 'video', 'x': 0, 'y': 0, 'w': 480, 'apiProvider': 'minimax-h3',
             'model': 'MiniMax H3', 'prompt': '女子向左走，无配乐。', 'duration': 5},
            {'id': 'film', 'type': 'film-video', 'x': 570, 'y': 0, 'w': 520, 'apiProvider': 'minimax-h3',
             'model': 'MiniMax H3', 'prompt': '女子向左走，无配乐。', 'duration': 5, 'actorCount': 1},
            {'id': 'ref', 'type': 'image', 'x': -360, 'y': 0, 'w': 300, 'url': '/static/assets/camera-reference/angle-eye-front.png', 'mediaKind': 'image'},
        ], 'connections': [
            {'id': 'ref-video', 'from': 'ref', 'to': 'video'},
            {'id': 'ref-film', 'from': 'ref', 'to': 'film', 'inputRole': 'storyboard'},
        ]}


fixture.project = project
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=3021)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), fixture.Handler)
    server.config_delay = server.capability_delay = 0
    server.fail_config_once = False
    print(f'LinkFox fixture: http://127.0.0.1:{args.port}', flush=True)
    server.serve_forever()
