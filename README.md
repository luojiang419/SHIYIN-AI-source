# SHIYIN AI
在线 API 图像、视频与对话创作工作台

## Windows x64 安装版

运行 `SHIYIN-AI-Setup-2.0.3.exe` 安装新的全量安装基准包，默认目录为 `D:\Program Files\SHIYIN AI`。程序资源位于安装根目录的 `app`，设置、数据库、媒体、缓存和日志写入同级 `data`。覆盖升级保留 `data`，后续更新通过独立局域网分发中心获取并校验热更新。

首次启动在引导页自行设置账号和密码。首个在安装软件的本机注册的账号为管理员，可以配置 API 与软件设置；后续注册的账号为普通账号。桌面端安全保存登录状态，后续启动无需重复登录；主动退出、切换账号或修改密码后才需重新登录。账号主要用于多人使用时的数据隔离，支持中文、英文字母和数字，英文字母不区分大小写，密码不能为空。注册后继续完成图片服务、AI助手及保存方式引导。

新用户安装包不带任何预置账号、API Key 或作品。管理员使用原有根数据目录，普通账号使用 `data/accounts/<内部ID>` 独立目录。旧版本覆盖安装后需要设置新的管理员账号，原管理员作品与配置保留；已有普通账号和数据不变。默认监听 3000 端口，可信局域网设备可通过显示的 `IP:3000` 注册或登录；必须先在本机完成管理员设置。请勿将端口直接映射到公网。

深度图、深度视频和 DWPose 等按需模型采用独立资源分发，首次使用时需要网络或对应离线资源；已下载模型在升级时保留。正式构建全量安装包使用 `npm run installer:build`，常规热更新使用 `npm run update:publish`。

高精度人物深度组件同样不内置进安装包：用户添加一键复刻或深度图节点后，若组件缺失会自动下载约 5.98GB 的分包；节点持续显示百分比、已下载/总量、来源与校验/安装阶段，完成后自动加载并继续生成深度图。组件保存在 `data/system/components/person-depth`，升级安装无需重复下载；下载需要约 13.2GB 可用磁盘空间，使用 `Depth Anything V2 Large (CC-BY-NC-4.0)` 与 `BiRefNet (MIT)`，仅限非商业用途。

1.0.x 历史版本使用当前全量安装基准包覆盖升级，不再使用旧桥接或热更新引导链。

可灵 CLI：Windows x64 安装版自带独立运行组件，无需安装 Node.js、npm 或全局 CLI。在普通视频或影视视频节点选择可灵后，点击“登录授权”；首次准备组件时选择中国区或海外区，继续后打开官方浏览器授权，完成后自动刷新账号与模型。已登录时点击“已授权”可查看账号 ID、会员和实时积分，用户名以官方返回为准；点击“切换授权”重新登录其他账号。浏览器未自动打开时可点击“打开授权页面”。源码版缺少组件时会按需下载并校验，保存到 `data/system/components/kling-cli`；已有全局 CLI 和登录状态仍可复用。局域网用户由本机管理员完成账号连接后使用。

配套的chrome采集插件已经上线：https://chromewebstore.google.com/detail/infinite-canvas-%E5%9B%BE%E5%83%8F%E8%A7%86%E9%A2%91%E6%96%87%E5%AD%97%E6%8A%93%E5%8F%96%E5%B7%A5/ajfhnbklbmpfaaookhfakohabnpmlcic?authuser=0&hl=en

详细教程：[https://youtu.be/1y9ShTvgC_w](https://youtu.be/r_y_9ALr7fg)

由于最近很多API网址关停，我找到一个稳定的网址：

https://apib.ai/register?aff=1uyAbb （包含所有生图模型/视频模型/LLM模型）

https://www.fhl.mom/register?aff=86L574B4T2N9  （包含codex和GPT image 2模型）

功能请求/功能更新/视频教程/联系我，都可以在B站评论或私信：https://space.bilibili.com/78652351

----

【新增了version文件，我每次更新都会更新version的版本号，如果你下载version文件，打开项目后，导航栏的GitHub按键就会提示新版本，如果不想查看更新提示，就删除version文件】

【A version file has been added. I update the version number with each update. If you download the version file, the GitHub button in the navigation bar will indicate the new version after opening the project. If you don't want to see update notifications, delete the version file.】

----

支持的功能：
1. 支持几乎所有OpenAI协议的API/异步协议/Gemini协议/方舟协议；API 设置输入后自动保存，无需额外勾选确认或点击保存
2. RunningHub的工作流/AI应用/收费模型调用
3. 火山引擎调用（人脸认证还在修复bug）
4. Modelscope免费LLM模型和图像模型调用
5. 即梦CLI调用，可直接调用即梦高级会员的积分，支持文生图/图生图/文生视频/图生视频
6. 扩展图片/360全景图预览截图/视频帧抽取/循环节点等诸多功能
7. tools文件夹中，增加了chrome批量采集到素材库的插件，PS直连画布调用所有功能的插件
8. 电商专用工作台：统一高品质生成，支持全能模式、自由换衣、动作迁移和批量换款；批量换款直接复用无限画布“一键复刻”节点的骨架、四输入和共享八组提示词，按款号组织多任务、查看/下载/删除组内作品，并自动归档到设置的“批量换款保存”目录下的款号子文件夹；Windows 桌面版参考素材坞可从资源管理器直接拖入多张图片并指定素材类型，同时保留参考图预览、裁切、版本切换和生成参数持久化
9. 软件设置：关闭窗口行为可选“最小化到托盘”或“退出软件”；生成图片保存位置可使用软件默认目录或自定义 Windows 文件夹，文件按 `SHIYIN-000001-YYYYMMDD` 连续编号；快捷保存可选手动保存或静默保存，媒体批量下载会选择一次目录并保存多个原始文件，不再打包 ZIP，静默模式则直接写入所选目录
10. 作品管理：集中浏览生成作品，支持搜索、类型筛选、收藏、下载，并可随时使用全屏划像对比核对细节
11. DWPose 本地姿态：CPU 识别多人身体、手部和面部关键点；模型国内镜像优先自动补齐、断点续传、SHA-256 校验并在升级后复用，本机管理员可查看进度与重试
12. 姿势参考节点：普通与智能无限画布均可使用本地 3D 人偶编辑 22 个骨骼、套用动作预设、调整机位与灯光，并导出多画幅 PNG 继续连接图片、视频或一键复刻节点；编辑过程不调用付费 API，编辑器完整适配浅色、深色、醇白和跟随系统主题

--------

已经申请著作权，禁止商业用途

Commercial use is prohibited.


* 可以自己使用和公司使用，禁止用于任何形式的修改封装成商业产品，商用须取得授权。

* 根据代码二次开发的软件必须保持开源并注明来源作者

* This software is for personal and company use only, but is prohibited from being modified or packaged into commercial products in any way. Commercial use requires authorization.

* Software developed based on this code must remain open source and the original author must be credited.

--------


<img width="2079" height="665" alt="image" src="https://github.com/user-attachments/assets/8469923b-f7a2-403c-9c37-e6e789211f28" />

<img width="1865" height="1503" alt="image" src="https://github.com/user-attachments/assets/f4030201-67c6-4845-b08b-b6fdf304afaa" />


<img width="1696" height="1350" alt="b68e144c5b04a322bfd035da4d89aba3" src="https://github.com/user-attachments/assets/0a6090fb-a8dd-4c3d-adee-b1f9233a2d91" />

   
<img width="1525" height="1473" alt="image" src="https://github.com/user-attachments/assets/6f61fcf9-746c-425b-9e36-cfc8d252da7c" />

   <img width="1261" height="864" alt="image" src="https://github.com/user-attachments/assets/57f3e230-3134-488f-8179-d97e7d15383a" />
<img width="1530" height="858" alt="image" src="https://github.com/user-attachments/assets/9990e42d-22d5-4a10-a1e1-ad35a634edd2" />

<img width="1735" height="1400" alt="image" src="https://github.com/user-attachments/assets/d8328ff8-bbe0-4f1c-9ffa-7b56e8a1a51d" />
<img width="2258" height="969" alt="image" src="https://github.com/user-attachments/assets/4a752d99-885d-4ba9-8b86-91b495786b5c" />


<img width="1531" height="1374" alt="image" src="https://github.com/user-attachments/assets/0af79e38-0955-4740-9e65-5c9bb057f58c" />

<img width="2196" height="1040" alt="image" src="https://github.com/user-attachments/assets/6d823668-cde2-4836-8332-1858efe5f520" />
<img width="2214" height="771" alt="image" src="https://github.com/user-attachments/assets/52e10958-753f-45ba-a50e-3bbec27be436" />
