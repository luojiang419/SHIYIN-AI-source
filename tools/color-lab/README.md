# 面料色彩验证台

运行：在项目根执行 `python tools/color-lab/server.py`，打开 http://127.0.0.1:13229。

上传参考图、生成原图，填写原图像素坐标 ROI（x,y,宽,高）。应用 ROI 当前为矩形，建议先用纯布面裁片验证。选择纯手动 Lab 偏移、Lab 仿射或 Lab 分位数，调滑块后点击生成预览。每次处理始终从上传原图开始，不累计上一次偏移。

保存面料名称后，参数与测量结果写入 `%LOCALAPPDATA%/SHIYIN-AI/color-lab/profiles.json`。下次选择档案恢复全部参数，再对新生成图复验。保存的是草稿，不承诺不同光照下稳定；像素坐标不会跨新图自动复用。原型尚未自动挂接一键复刻任务。

验证：`node tools/color-lab/verify.cjs`，真实布面裁片上传、亮度调整、生成结果、保存和重新加载；截图 verification.png。验证会创建一条明确命名的测试档案。
