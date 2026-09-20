"""从本次真实素材裁切对照区域，保留原像素与可追溯坐标。"""
import json
from PIL import Image

def build_details(out):
    assets=out/'assets'; manifest=[]
    # 同一设计部位分别取景；不做配准、补绘、锐化或缩放。
    groups=[
      ('棕色裤装：面料斜纹','验收未通过：生成图偏红、偏灰，斜纹更细、更平，未还原实拍面料的厚实质感。拍摄距离不同会影响纹理大小，但不能据此忽略整体颜色与材质差异。',[
        ('b-detail.jpg',(600,1500,1250,2150),'实拍面料'),('b-product-fixed.png',(1450,2100,2100,2750),'批量生成 · 边界修复版'),('b-node-fixed.png',(1450,2100,2100,2750),'一键复刻 · 边界修复版')]),
      ('棕色裤装：后腰双扣与腰耳','验收未通过：这组不仅要看双扣和腰耳，还要看底布。批量生成图的颜色与织物质感明显偏离实拍；双扣存在不代表商品还原合格。',[
        ('b-detail.jpg',(620,200,1070,550),'实拍双扣与腰耳'),('b-product-fixed.png',(1470,820,2020,1220),'批量生成双扣'),('b-node-fixed.png',(1470,820,2020,1220),'一键复刻双扣')]),
      ('棕色裤装：皮牌与侧边扣件','对照皮牌的长宽、位置、文字和旁边的扣件。生成图中的文字不能视为准确品牌标识。',[
        ('b-detail.jpg',(1230,200,1620,600),'实拍皮牌与扣件'),('b-product-fixed.png',(2020,780,2430,1210),'批量生成皮牌'),('b-node-fixed.png',(2020,780,2430,1210),'一键复刻皮牌')]),
      ('棕色裤装：后袋形状与车线','对照袋口角度、袋底轮廓、双线走向及袋位。成图虽保留后袋，不能只凭“有口袋”就判定设计还原。',[
        ('b-detail.jpg',(700,600,1430,1350),'实拍后袋'),('b-product-fixed.png',(1560,1180,2180,1840),'批量生成后袋'),('b-node-fixed.png',(1560,1180,2180,1840),'一键复刻后袋')]),
      ('黑白豹纹：花纹与面料绒感','核对花纹形状、疏密、浅色底和绒感。局部清晰度与整件衣服的花纹一致性需要分别判断。',[
        ('a-detail.jpg',(600,600,1250,1250),'实拍豹纹面料'),('a-product-result.jpg',(1450,1800,2100,2450),'生成豹纹局部')]),
      ('牛仔上衣：胸袋、袋盖与纽扣','旧样张材质验收未通过：实拍的粗斜纹、经纬交织和橙黄色车线没有准确保留，生成图偏细碎、泛白。不能用穿着角度与褶皱解释这些差异。',[
        ('a-style-c.jpg',(2120,1270,2920,2220),'实拍左胸袋'),('a-style-c-result.jpg',(1150,1730,1790,2500),'生成左胸袋')]),
      ('牛仔上衣：下摆毛边与收口','原款本身带有毛边。应核对毛边长度、分布和下摆轮廓；此前“生成新增毛边”的表述已纠正。',[
        ('a-style-c.jpg',(2050,3390,4170,3700),'实拍毛边下摆'),('a-style-c-result.jpg',(1050,3200,2560,3650),'生成毛边下摆')]),
    ]
    if (assets/'b-software-node-rerun.png').exists():
        groups.append(('真实软件重新生成：腰头与面料复核','两次均通过已安装软件实际提交：批量页使用内置模板；一键复刻增加颜色与材质要求。两次输出仍偏红、纹理平铺感明显，均未通过材质验收。未使用外部修图替换软件结果。',[
            ('b-detail.jpg',(620,200,1070,550),'实拍原款'),
            ('b-software-rerun.png',(1470,820,2020,1220),'软件批量页重生 · 未通过'),
            ('b-software-node-rerun.png',(1470,820,2020,1220),'软件一键复刻重生 · 未通过')]))
    if (assets/'denim-software-node-1.jpg').exists():
        groups.append(('牛仔上衣：真实软件重新生成复核','本轮已给牛仔款单独绑定原款胸袋细节，并在一键复刻中补充材质要求。以下两张仍有织纹偏细、车线偏灰的问题，未通过高标准材质验收；不作为总览轮播的成功样张。图片均为软件实际输出，未经外部增强。',[
            ('denim-reference-detail.png',(0,0,750,1000),'原款胸袋与织纹'),
            ('denim-software-rerun-1-1.jpg',(1180,1780,1780,2460),'批量页重生 · 未通过'),
            ('denim-software-node-1.jpg',(1220,1880,1820,2580),'一键复刻重生 · 未通过')]))
    if (assets/'denim-software-fixed-runtime.jpg').exists():
        groups.append(('牛仔上衣：补充要求修复后实测','修复版软件已通过正常补充要求检查并完成生成；本次在隔离验证环境运行。新图仍有车线偏灰、织纹偏细的问题，材质验收未通过。检查问题修复不等于商品还原合格。',[
            ('denim-reference-detail.png',(0,0,750,1000),'原款胸袋与织纹'),
            ('denim-software-fixed-runtime.jpg',(1180,1750,1840,2510),'修复版软件实测 · 材质未通过')]))
    if (assets/'denim-software-node-2.jpg').exists():
        groups.append(('牛仔上衣：安装版更新后验收','安装版应用热更新 20260920214122 后，以同一组近照和补充要求重新生成，正常通过检查并出图。下图为安装版直接输出，车线与织纹仍未达到原款材质要求，不作为成功样张。',[
            ('denim-reference-detail.png',(0,0,750,1000),'原款胸袋与织纹'),
            ('denim-software-node-2.jpg',(1180,1750,1840,2510),'更新后安装版 · 材质未通过')]))
    content=[]
    for n,(title,note,entries) in enumerate(groups):
        cards=[]
        for j,(source,box,label) in enumerate(entries):
            name=f'compare-{n+1}-{j+1}.png'
            with Image.open(assets/source) as im:
                assert 0<=box[0]<box[2]<=im.width and 0<=box[1]<box[3]<=im.height,(source,box,im.size)
                im.crop(box).save(assets/name)
            w,h=box[2]-box[0],box[3]-box[1]
            manifest.append(dict(source='assets/'+source,box=box,output='assets/'+name,size=[w,h],resampled=False))
            cards.append(f'<figure><figcaption><b>{label}</b><span>{w} × {h} px</span></figcaption><div class="pixel-window"><button class="photo" data-src="assets/{name}" data-title="{title} · {label}" aria-label="放大：{title} · {label}"><img src="assets/{name}" alt="{label}" width="{w}" height="{h}"></button></div><a href="assets/{source}" download>下载对应完整原图</a></figure>')
        content.append(f'<article class="case detail-case"><h2>{title}</h2><p>{note}</p><div class="pixel-grid" style="--columns:{len(entries)}">'+''.join(cards)+'</div></article>')
    (out/'evidence/detail-comparison-crops.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return '<section class="panel" id="pixels" hidden><span class="eyebrow">实拍与生成细节对照</span><h1>100% 细节对比</h1><p class="lead">将实拍商品与本次生成结果并排检查，重点确认面料和特色设计是否保留。</p><p class="note">100% 模式下，1 个图片像素对应 1 个 CSS 像素，请将浏览器缩放设为 100%。所有局部均直接裁自原图，未缩放或修饰；拍摄距离和角度不同，不代表实物处于相同比例。裤装生成图为已说明的边界修复版。</p><div class="pixel-toolbar"><button id="pixelsNative" aria-pressed="true">100% 原始像素</button><button id="pixelsFit" aria-pressed="false">适应窗口</button><span>拖动滚动条查看局部，点击图片可全屏缩放对照。</span></div>'+''.join(content)+'<a href="evidence/detail-comparison-crops.json" download>下载裁切来源与坐标记录</a></section>'
