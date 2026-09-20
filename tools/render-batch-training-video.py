"""将本轮真实图片/界面截图编排为带字幕和动态进度的教学视频。"""
import json,re,math,subprocess
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'案例/批量复刻培训-20260920'
text=(OUT/'index.html').read_text(encoding='utf-8')
steps=json.loads(re.search(r'const demoSteps=(.*?);const tabs=',text,re.S).group(1))
fontpath='C:/Windows/Fonts/msyh.ttc'
font=lambda n:ImageFont.truetype(fontpath,n)
W,H,FPS,SECONDS=1600,1000,12,7
proc=subprocess.Popen(['ffmpeg','-y','-loglevel','error','-f','rawvideo','-vcodec','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','21','-pix_fmt','yuv420p','-movflags','+faststart',str(OUT/'操作演示.mp4')],stdin=subprocess.PIPE)
def wrap(draw,t,x,y,width,ft,fill):
    line=''
    for ch in t:
        if draw.textlength(line+ch,font=ft)>width:
            draw.text((x,y),line,font=ft,fill=fill);y+=43;line=ch
        else:line+=ch
    draw.text((x,y),line,font=ft,fill=fill)
for idx,s in enumerate(steps):
    base=Image.new('RGB',(W,H),'#f4f3ed');d=ImageDraw.Draw(base)
    d.rectangle((0,0,W,105),fill='#163d34');d.text((55,27),'拾影  /  一键复刻 × 批量换款',font=font(29),fill='white')
    d.text((1200,35),'真实案例 · 操作教学',font=font(22),fill='#d4e5d9')
    d.text((55,128),f'{idx+1:02d}  {s["title"]}',font=font(40),fill='#203b30')
    n=len(s['images']);cell=(W-110-(n-1)*20)//n
    for j,src in enumerate(s['images']):
        im=Image.open(OUT/src).convert('RGB');im=ImageOps.contain(im,(cell,565),Image.Resampling.LANCZOS)
        x=55+j*(cell+20)+(cell-im.width)//2;y=218+(565-im.height)//2
        base.paste(im,(x,y));d.text((55+j*(cell+20),792),s['labels'][j],font=font(19),fill='#52655b')
    wrap(d,s['text'],55,835,1490,font(26),'#334b40')
    d.text((55,955),'教学动画：真实素材与页面截图编排，非连续录屏，等待时间已压缩。',font=font(17),fill='#64736a')
    d.text((1390,955),f'{idx+1} / {len(steps)}',font=font(17),fill='#64736a')
    for frame in range(FPS*SECONDS):
        img=base.copy();q=ImageDraw.Draw(img);progress=(idx+frame/(FPS*SECONDS))/len(steps)
        q.rectangle((0,992,int(W*progress),999),fill='#477c50')
        if n==1:
            px=1060;py=650;radius=18+int(6*math.sin(frame/FPS*4))
            q.ellipse((px-radius,py-radius,px+radius,py+radius),outline='#c5de72',width=4)
            q.polygon([(px,py),(px+4,py+29),(px+11,py+20),(px+24,py+19)],fill='#fff',outline='#1b3929')
        proc.stdin.write(img.tobytes())
proc.stdin.close();assert proc.wait()==0
print('56 seconds / 1600x1000 / H.264 / no audio')
