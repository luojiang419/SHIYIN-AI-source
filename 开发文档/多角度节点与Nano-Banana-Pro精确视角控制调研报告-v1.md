# 多角度节点与 Nano Banana Pro 精确视角控制调研报告

状态：调研完成
最后更新：2026-08-30

## 结论先行

在 Nano Banana Pro（Gemini 3 Pro Image）上，当前最可靠的路线不是把 3D 滑块的数值直接当作“相机 API 参数”传入，而是：

1. 用原图作为唯一主体参考；
2. 把角度转换成简短、无歧义的英文“最终机位 + 目标方向”描述；
3. 每个角度单独生成，选出一个合格视图后再作为下一角度的附加参考，控制身份漂移；
4. 对产品、建筑或需要严格透视的任务，先用真实 3D/深度代理渲染目标机位，再让 Nano Banana Pro 只做材质和风格还原。

如果目标是“输入任意 40°，模型必须几何上准确地转 40°”，Nano Banana Pro API 目前没有公开的连续 yaw/pitch 控制接口，单靠节点或提示词不能提供渲染器级保证。专用多角度 LoRA（例如 Qwen-Image-Edit-2511 Multiple-Angles）在其支持的 96 个离散姿态内更接近可控相机，但它不是 Nano Banana Pro，不能直接替代 NBP。

## 1. 官方能力与限制

Google 将 Nano Banana Pro 定位为复杂图像编辑和多轮创作模型，支持高分辨率、局部编辑、相机角度调整和多参考图；Gemini 3 Pro Image 最多 6 张对象高保真参考图、5 张人物一致性参考图，最多 14 张总输入。官方“360 view”示例采用迭代方式：先生成一个角度，再把之前生成的图放入后续请求，而不是一次请求期待连续的 360°相机轨道。[Gemini 图像生成 API 文档](https://ai.google.dev/gemini-api/docs/generate-content/image-generation)

官方文档给出的相机提示模板是“镜头类型 + 场景 + 光线 + camera angle + lens”，重点是自然语言的最终画面，而不是数值字段。[Gemini 图像生成 API 文档](https://ai.google.dev/gemini-api/docs/image-generation?authuser=108&hl=en) Google 的产品介绍虽然宣称可以调整 camera angles，但没有公开 yaw、pitch、roll 或镜头内参的可编程参数。[Nano Banana Pro 产品介绍](https://blog.google/innovation-and-ai/products/nano-banana-pro/)

官方 API 还明确说明：模型不一定遵守请求的输出张数，Gemini 3 Pro 的高保真参考图数量有限，所有生成图带 SynthID 水印。这些限制意味着“节点批量生成九个角度”不能被当作九个严格相机渲染结果。

## 2. 当前项目的实际问题

### 2.1 节点数值没有进入图像模型的原生相机通道

当前 [static/js/canvas.js](../static/js/canvas.js) 的 `generateClassicSpecialEdit` 只发送 `prompt`、`operation:'angle_change'`、`style_reference_url` 和参考图；`angleAzimuth`、`angleElevation`、`angleDistance` 没有作为独立 API 字段发送。当前在线图片请求模型也没有相机姿态字段，因此数值只能通过最终提示词间接表达。

### 2.2 40°存在左右语义冲突

当前 [static/js/canvas-special-nodes.js](../static/js/canvas-special-nodes.js) 将水平角定义为：0°正面、90°右侧、270°左侧；40°会被 `nearestAzimuth` 归类为 `front-right quarter view`。同时 `angleOrbitInstruction(40)` 会写入“向 Image 1 的 camera-right basis 移动”。如果用户输入“左侧40度”，这套坐标会把同一个数值解释成右前方，节点结果当然可能与直接提示词相反。这是最值得优先修复的确定性问题。

### 2.3 提示词过长且含有多组相互竞争的目标

`buildAnglePrompt` 当前包含“冻结 3D 场景、丢弃 2D 投影、重建遮挡、世界坐标锁、镜像锁、颜色统计校准、有效性测试”等多段指令。它们对传统可编程渲染器有意义，但 NBP 仍是指令式图像模型；过多的否定句、抽象 3D 术语和“保持近似同一画面区域”会与“重新投影”竞争。社区对 NBP 的经验也显示，明确的最终机位和画面内容通常比抽象的“自然视差/围绕旋转/保持世界坐标”更有效。[Nano Banana 2/Pro 空间覆盖提示经验](https://www.reddit.com/r/nanobanana/comments/1vvmj71/i_made_a_nano_banana_2_prompt_for_getting/)

### 2.4 风格校准不能修复几何错误

后端在 `operation == 'angle_change'` 后执行 `harmonize_generated_image_style`，它只能拉近 RGB 均值和方差；它无法把错误的左侧视角变成正确的左侧视角，也无法补回模型看不到的背面几何。

### 2.5 不能把 NBP 当成可重复渲染器

Gemini API 的图像生成没有公开 seed 或连续相机轨道参数。相同图片和相同文字可能出现不同细节；官方建议用多轮图像编辑和前一张结果作为参考。Google AI Developers Forum 中，用户报告 AI Studio 网页端与 REST API 在主体锁定和编辑质量上存在差异；Google 工程师回复称无法复现，并建议提供完整请求和输入输出，说明该问题尚无公开的 API 级解决方案。[论坛讨论](https://discuss.ai.google.dev/t/title-critical-inconsistency-gemini-3-pro-image-nano-banana-pro-editing-performance-disparity/112093)

## 3. 全网方案比较

| 方案 | 角度控制机制 | 对 NBP 的直接兼容性 | 角度精度 | 一致性 | 主要问题 |
|---|---|---:|---:|---:|---|
| 简短语义提示词 | “camera-left 40-degree three-quarter view…最终画面” | 高 | 中（语义近似） | 中 | 看不见的表面会被猜测，不能保证精确 40° |
| 当前多角度节点 | 3D UI → 方向词/数值 → 长提示词 | 高 | 低到中 | 中 | 节点不注入相机参数；方向映射可能反向；长提示词稀释重点 |
| NBP 多轮迭代 | 原图→目标角度→把合格结果作为下一次参考 | 高 | 中 | 中到高 | 成本和延迟随角度数增加；会累积漂移 |
| 3D/深度代理 + NBP | Blender/Load3D/深度图先确定投影，再用 NBP 做材质修复 | 间接 | 高（取决于代理） | 高 | 需要模型或深度；背面空洞仍需生成；流程复杂 |
| Qwen-Image-Edit-2511 + Multiple-Angles LoRA | 训练过的离散相机姿态 token | 不兼容 NBP（需换模型） | 高（96 个离散姿态） | 中到高 | 需要本地显存/不同模型；不是连续角度；LoRA 触发词和顺序严格 |
| 直接输出 3×2/3×3 角度网格 | 一次提示生成多个视图 | 高 | 低到中 | 低到中 | 每格不是独立严格相机；产品细节和身份容易漂移 |

### 3.1 专用多角度 LoRA 是“可控角度”最强的公开证据

FAL 发布的 `Qwen-Image-Edit-2511-Multiple-Angles-LoRA` 用 3000+ Gaussian Splatting 渲染对 96 个姿态训练（8 方位 × 4 高度 × 3 景别），要求 `<sks> [azimuth] [elevation] [distance]` 的固定顺序，建议 LoRA 强度 0.8–1.0。[Hugging Face 模型卡](https://huggingface.co/fal/Qwen-Image-Edit-2511-Multiple-Angles-LoRA)

这证明“节点滑块真正有效”的关键在于模型训练过相机姿态条件，而不是 UI 是否是 3D。`ComfyUI_CameraAngleSelector` 和 `ComfyUI-qwenmultiangle` 都只是把 96 个合法组合可视化并输出正确触发词；它们并没有给 NBP 增加隐藏的相机控制能力。[CameraAngleSelector 说明](https://www.runcomfy.com/comfyui-nodes/ComfyUI_CameraAngleSelector)、[Qwen 多角度节点](https://github.com/jtydhr88/ComfyUI-qwenmultiangle)

### 3.2 深度/3D 代理路线最接近几何正确

社区实践通常是 Load3D 或 Blender 先摆好相机，输出渲染图、深度图或法线图，再交给具备结构控制的编辑模型。一个典型讨论中，用户把 3D 场景渲染作为第一张参考、深度图作为第二张参考，利用 Qwen Edit 的控制条件重建视角；反馈是“效果不错，但遮挡处会偏移”。[ComfyUI 讨论](https://www.reddit.com/r/comfyui/comments/1polrne/qwen_edit_camera_control_angle/)

该路线对 NBP 的正确用法是：让 NBP 负责“把代理渲染变成真实照片、保持原图材质/身份”，不要让 NBP 独自承担精确几何变换。代理越接近真实 3D，角度越准；代理缺失的背面、透明件和细小结构仍然需要模型补全。

## 4. 社区评论归纳

* **“一个节点不会凭空产生真正的 turnaround。”** Reddit 用户建议先锁定主体，再逐角度生成，并使用 pose/depth/edge 引导；把它当作角色表制作，而不是一次请求四个随机角度。[讨论](https://www.reddit.com/r/comfyui/comments/1tuec5h/how_can_i_generate_multiple_camera_anglesviews/)
* **Qwen LoRA 的反馈总体积极，但承认是离散姿态。** VNCCS 节点作者称只要把相机控制节点接到普通 Qwen Edit 工作流即可；用户反馈“works like a charm”，但也有人指出 45°间隔太大，希望有 10°/15°前向角度。[讨论](https://www.reddit.com/r/comfyui/comments/1q76sy5/visual_camera_control_node_for/)
* **LoRA 与 ControlNet 的取舍。** 社区回复认为多角度 LoRA 适合近似重新构图，但不能像 ControlNet 那样精确控制相机和镜头；需要精确透视时应使用深度/法线/线稿等结构条件。[讨论](https://www.reddit.com/r/comfyui/comments/1polrne/qwen_edit_camera_control_angle/)
* **NBP 用户更倾向于“最终机位描述”。** 近期 Nano Banana 经验贴明确建议写“把相机放在房间某个已知位置并对准某个地标”，少写“旋转120°、自然视差、保持互惠地理”等抽象运动指令；作者称这比单纯写“rotate camera 90 degrees”稳定。[经验贴](https://www.reddit.com/r/nanobanana/comments/1vvmj71/i_made_a_nano_banana_2_prompt_for_getting/)
* **API 与网页端差异仍是未解决问题。** Google 开发者论坛中，多位用户报告同图同提示在 AI Studio 与 API 的主体锁定、阴影和材质一致性不同；官方回复未确认存在单独的未公开 inpaint 端点。[论坛](https://discuss.ai.google.dev/t/title-critical-inconsistency-gemini-3-pro-image-nano-banana-pro-editing-performance-disparity/112093)

## 5. 可行性排序

### 第一名：NBP 专用“语义机位编译器”+ 多轮参考

适合当前项目，改动小且与现有 API 兼容。节点输出应遵循：

```text
Recreate the supplied image as the same physical subject and scene.
Place the camera 40 degrees to the subject's left (camera-left), at the same height and distance, eye-level, 50mm perspective. Show the new left three-quarter view with the subject's left-side surfaces and occlusions visible. Keep identity, proportions, clothing/materials, lighting and background consistent. Do not mirror the image.
```

关键是“camera-left + 最终画面中应出现的表面/遮挡”，而不是仅输出 `yaw=40`。对人物要锁定脸、发型、服装和身体朝向；对产品要锁定 logo、接口、缝线和非对称部件。每个角度单独请求，合格结果作为下一角度的第二参考图；不要一次把 8 个角度塞进同一请求。

### 第二名：3D/深度代理 + NBP 精修

这是产品 SKU、建筑空间、机械件和需要 90°/180°背面时的首选。先在 Blender/Load3D/NeRF/点云中固定模型和相机，输出目标角度的基础投影，再让 NBP 做材质、光照、真实感和局部缺失补全。它的几何上限最高，但素材准备、遮挡处理和成本都更高。

### 第三名：改用 Qwen 多角度 LoRA 生成角度，再交给 NBP

当用户接受双模型流程时，这条路线在 96 个训练姿态内比 NBP 直接提示更可控：Qwen 负责角度，NBP 负责最终风格或电商质感。不能把 Qwen 的 96 姿态 token 直接喂给 NBP 期待同样效果。

### 不建议作为精确方案：一次生成多格角度图

它适合做概念板、选角度和人工挑图，不适合作为可验收的多视图资产。官方也提醒模型不总是遵守输出数量；多格布局会增加每格分辨率下降、身份漂移和产品文字错误的风险。

## 6. 对当前节点的具体改造建议

1. **修正坐标语义。** 采用 `left=-40° / right=+40°` 的有符号角度，或在 UI 中明确“0°正面、正值右转、负值左转”。不要再让 40°同时代表“左40°”和“右前45°”。
2. **分离 NBP 模式与 LoRA 模式。** NBP 模式只输出自然语言最终机位；Qwen LoRA 模式才输出固定 `<sks>` token。节点名称和提示词模板必须显示当前模式。
3. **把提示词压缩到 45–90 个英文词。** 顺序使用：相机位置/朝向 → 画面内容 → 深度关系 → 身份与材质保持 → 光线与画幅。删除“丢弃 2D 投影、RGB 统计校准、有效性测试”等模型无法执行的元指令。
4. **增加“相机位置锚点”字段。** 让用户选择“主体左前方/主体右后方/房间门口/桌面左侧”等终点；对空白背面要求模型会更可靠。对于场景，使用门、窗、墙角、道路边缘等已知地标。
5. **增加两阶段模式。** 第一阶段只生成目标角度草图/低成本预览；用户选中后，第二阶段把原图和合格角度一起送入 NBP 做 2K/4K 精修。这样比每次从原图重新猜背面更稳定。
6. **增加结构参考端口。** 可选输入深度、法线、线稿或 3D 渲染图；NBP 仍作为最终图像模型，但节点要明确这不是 NBP 的原生相机控制。
7. **增加可验收指标。** 记录请求角度、左右语义、景别、使用的参考图数量和最终提示词；输出人工检查项：方向是否正确、主体身份、非对称部件、遮挡关系、透视/地平线、logo 文字、背景连续性。

## 7. 最终判断

对“只使用 Nano Banana Pro、希望比当前节点更稳定”的需求，最高可行性是**简短英文语义机位 + 原图/前一合格视图多轮参考**；它能显著优于当前长提示词，但仍是生成式近似，不是精确渲染。

对“必须精准得到任意 40°/90°/180°产品视角”的需求，最高可行性是**真实 3D/深度代理确定几何，再由 NBP 做外观精修**。如果不接受 3D 资产准备，则应接受角度为离散近似，并优先考虑 Qwen 多角度 LoRA 这类真正经过姿态训练的模型，而不是继续增加 NBP 节点中的数字和否定词。

## 8. LoRA 对画质与 16GB 显存的影响

### 8.1 LoRA 会不会降低画质

多角度 LoRA 是约 295MB 级别的适配器，主要改变相机姿态条件，不会像把主模型换成低清模型那样必然降低画质。正确加载在 Qwen-Image-Edit-2511 上、强度从 0.8–0.9 开始时，通常能换来更稳定的视角命中；但它可能带来轻微的构图偏置、细节重绘或纹理变化，尤其是目标角度不在训练的 96 个离散组合内时。[模型卡](https://huggingface.co/fal/Qwen-Image-Edit-2511-Multiple-Angles-LoRA)

画质的主要决定因素是主模型精度和工作流设置：社区测试认为 FP8 主模型质量高于低位数 GGUF，Q6 及以下量化会出现可见质量下降；Lightning 蒸馏 LoRA 可能造成塑料皮肤和过度平滑，应先用普通 20 步工作流验证角度，再考虑加速。[Qwen Edit 质量测试](https://www.reddit.com/r/comfyui/comments/1tqm4pb/cracked_the_case_on_high_res_quality_qwen_edit/)

### 8.2 16GB 显存能否运行

可以运行，但要区分“能启动”和“高质量、速度可接受”：

| 配置 | 16GB 显存可行性 | 预期 |
|---|---|---|
| Qwen Edit 2511 BF16/FP8 全量 + 多角度 LoRA | 不推荐直接全显存运行 | 通常需要更大显存或大量系统内存 offload |
| Q4/Q5 GGUF + 多角度 LoRA | 可以 | 角度功能可用，速度中等，画质低于 FP8 |
| Q3 GGUF + 多角度 LoRA | 可以，最稳妥的低显存方案 | 画质进一步下降，但社区已有 16GB 显卡成功运行案例 |
| 低分辨率预览后再高分辨率精修 | 推荐 | 先验证角度，减少显存和等待时间 |

社区有 16GB RTX 5060 Ti 使用 Q3 量化运行多角度工作流的案例；另有测试指出 FP8 模型约 22GB，依靠 ComfyUI block swapping 可以在低于 24GB 显存上运行，但系统内存越少越慢，建议至少 32GB RAM。[16GB 运行案例](https://www.reddit.com/r/StableDiffusion/comments/1v576c1/qwen_multi_angle_workflow/)、[FP8/GGUF 显存测试](https://www.reddit.com/r/comfyui/comments/1tqm4pb/cracked_the_case_on_high_res_quality_qwen_edit/)

### 8.3 推荐的 16GB 配置

* 主模型：Qwen-Image-Edit-2511 的 Q4_K_M 或 Q3 GGUF；如果系统内存达到 32GB 以上，可尝试 FP8 + block swapping。
* 多角度 LoRA：`fal/Qwen-Image-Edit-2511-Multiple-Angles-LoRA`，强度从 0.85–0.9 开始。
* 文本编码器：尽量使用官方 FP8 `qwen_2.5_vl_7b_fp8_scaled`，不要再叠加低精度文本编码器。
* 生成策略：先用 768–1024 边长、10–15 步测试角度；确认方向正确后再提高到 1K/2K 和 20 步。
* 不建议一开始叠加 Lightning LoRA；它虽然省时间，但可能明显损失皮肤和材质质感。

因此，16GB 显卡适合把该 LoRA 当作“角度验证和批量预览工具”。若最终交付要求最高纹理质量，建议用 16GB 本地显卡确定角度，再用更高显存机器或云端 FP8/BF16 工作流完成最终渲染。

## 9. 不使用 LoRA 的方案与社区试验反馈

### 9.1 方案对比

| 路线 | 是否需要 LoRA | 角度控制上限 | 社区反馈 | 主要问题 |
|---|---:|---|---|---|
| NBP 短提示词 + 单角度逐次生成 | 否 | 语义近似，不能保证精确 40° | 易用，简单提示常能命中左/右三分之四视角 | 大角度、背面和遮挡区域会漂移 |
| Qwen-Image-Edit-2511 原生模型 + 提示词 | 否 | 比 NBP 更适合编辑，但仍是生成式近似 | 有用户反馈单图“move the camera angle”效果很好；90°时加“to obtain the side view”更容易成功 | 不同图像、量化和采样设置差异大，没有 96 个离散姿态 token 的稳定性 |
| 深度/法线/线稿 ControlNet + 编辑模型 | 否（但通常不是 NBP 原生能力） | 结构约束较强 | 社区认为比 LoRA 更接近真实相机/镜头控制 | 需要额外结构图；深度错误会把错误透视带入结果 |
| Blender/Load3D/NeRF/TripoSplat 先定机位，再用 NBP 精修 | 否 | 几何最强，可任意角度 | “works pretty well”，是产品、建筑和机械件最稳路线；TripoSplat + Qwen/NBP 被反馈为快速得到新角度 | 建模、遮挡补洞和人工操作成本最高 |

### 9.2 社区试验的真实结论

* **纯提示词是“能用”，不是“可验收的精确控制”。** Qwen 2511 社区有人在有无 LoRA 两种情况下得到近似相同结果，说明基础模型本身具备视角编辑能力；但 90°等大变化需要补充“side view”等画面语义，结果仍会随主体和构图变化。[Qwen 2511 无 LoRA 讨论](https://www.reddit.com/r/comfyui/comments/1pvj4u6/qwenimageedit2511_workflow_that_actually_works/)
* **NBP 的短、具体机位描述通常优于节点生成的长抽象指令。** 用户试验建议写最终相机所在位置、朝向和可见地标，少写“旋转 120°、自然视差”等模型无法直接执行的抽象约束；这与 Gemini 官方提供的“camera angle + subject + lighting + composition”提示结构一致。[NBP 社区试验](https://www.reddit.com/r/nanobanana/comments/1vvmj71/i_made_a_nano_banana_2_prompt_for_getting/)、[Gemini 图像生成文档](https://ai.google.dev/gemini-api/docs/generate-content/image-generation)
* **深度/3D 路线的反馈最接近“真正换相机”。** Load3D 用户用 3D 渲染图加深度图作为参考，反馈整体“works pretty well”，但遮挡处仍会出错；TripoSplat 方案则先从单图估计 Gaussian Splat，再旋转 GLB 相机，最后让编辑模型补材质和缺失区域。[Load3D + 深度讨论](https://www.reddit.com/r/comfyui/comments/1polrne/qwen_edit_camera_control_angle/)、[TripoSplat + Qwen 讨论](https://www.reddit.com/r/comfyui/comments/1tx5ynt/triposplat_qwen_w_lora_move_to_any_new_camera/)
* **多角度拼图/六宫格能保持大致身份，但不能替代逐张生成。** 社区展示过 NBP 一次生成多角度网格的成功案例，适合选方案和做概念板；它会牺牲单格分辨率，并增加角度、文字和身份漂移，不适合作为产品多视图交付。[NBP 多角度试验](https://www.reddit.com/r/AiGeminiPhotoPrompts/comments/1qxx91n/how_to_create_6_different_camera_angles_from_a/)

### 9.3 对当前项目的推荐

如果坚持 **不使用 LoRA 且必须使用 Nano Banana Pro**，建议采用“**语义机位编译器 + 单角度多轮参考 + 可选深度/3D 结构参考**”三层模式：

1. 节点把 `left/right`、目标角度、机位高度、距离和镜头感翻译成 45–90 个英文词；提示词明确 `camera-left` 或 `camera-right`，并写出“应露出的侧面”和“自然遮挡”。
2. 每次只生成一个角度；通过验收的角度作为下一轮的第二参考图，减少从原图直接猜背面的漂移。
3. 需要 90°以上、产品非对称细节或可复现相机轨迹时，先接入 3D/深度渲染，再让 NBP 负责外观重建。

推荐测试提示词：

```text
Use the uploaded image as the identity and material reference. Place the camera 40 degrees to the subject's left (camera-left), at the same height and distance, eye-level, 50mm perspective. Show a clear left three-quarter view; reveal the subject's left-side surfaces and natural occlusion. Keep identity, proportions, clothing, materials, lighting and background consistent. Do not mirror the image.
```

该路线的可行性高于当前“把 40°数字直接传给节点”的做法，但仍不能承诺每张图都严格等于物理 40°。若验收标准是可重复的任意角度，必须引入深度/3D 几何约束，或接受 Qwen 多角度 LoRA 的离散角度方案。

## 10. NBP 语义模式五轮实测

使用原图 `D:\data\图片\20260820-195103.png`，通过 imgx 调用 `gemini-3-pro-image-preview`，画幅 `3:4`、分辨率 `2K`，五个角度均以原图作为 Image 1 独立生成：

| 目标角度 | 实测表现 | 判断 |
|---|---|---|
| 左 20° | 有明显左侧三分之四变化，身份和服装保持好，但实际幅度偏大 | 中等 |
| 左 40° | 左侧三分之四清楚，项链、腰带、豹纹夹克和背景连续 | 较好 |
| 左 60° | 有侧向变化，但独立采样中出现接近正面的结果 | 部分命中 |
| 左 90° | 左侧面轮廓清晰，侧视语义执行良好 | 强命中 |
| 左 120° | 后左三分之四/背面清晰，夹克背部图案连续 | 强命中 |

五轮成功率为 5/5，但这组测试也验证了：NBP 可以可靠区分“前方、侧面、背面”三个大区间，不能把连续角度数字当作物理旋转量。20°–60°更适合被解释为“轻微/中等左侧三分之四”，90°以上应使用 `true left side view` 或 `rear-left three-quarter view` 等结果导向语义。测试输出目录为 `E:\APP\SHIYIN-AI\generated-images\20260830-nbp-angle-5rounds`，详细 manifest 记录了每轮提示词和文件。


## 11. 不使用 LoRA 的节点内深度/3D 参考增强

本项目已落地一条不依赖 LoRA 的几何参考路径：角度节点提供“无（语义模式）/自动深度图/3D 导演台截图”三种模式。自动深度图使用 MiDaS Small ONNX，首次启动或首次调用时下载约 66 MB 权重，CPU ONNX 推理输出与原图同尺寸的相对深度灰度 PNG。模型输入输出和 MIT 许可信息以 [MiDaS Small ONNX 模型卡](https://huggingface.co/Heliosoph/midas-small-onnx) 为准；后续若更重视远处细节，可评估 [Depth Anything V2 官方实现](https://github.com/DepthAnything/Depth-Anything-V2)，但其部署体积、许可和 CPU 成本更高。

3D 路径默认在角度生成前向已连接的 3D 导演台请求当前活动视角的实时渲染图。父子窗口通过 `storyai:director-capture-request` / `storyai:director-capture-response` 传递 `preset:"current"` 截图；父窗口上传后写入导演台节点捕获列表和角度节点的 `angleDirectorCaptureUrl`。导演台未打开时会临时打开并在截图完成后关闭；超时或渲染失败时回退到最近一次已保存截图，不阻断普通生成。角度节点可同时连接原图和导演台节点：原图始终是 Image 1，导演台截图作为 Image 2 的几何参考，不会抢走人物身份输入。请求顺序为“原图 → 深度图/导演台截图 → 上一轮已接受结果”，提示词明确第二张图只约束轮廓、近远层次、遮挡和透视。这样能让 Nano Banana Pro 使用现有图像参考接口，不需要把 GLB 直接上传给模型。

当前仍有两项边界：第一，NBP 对深度图和导演台截图都是软条件，不能像 ControlNet 一样逐像素锁定相机射线；第二，导演台场景与原图主体不一致时，模型仍可能需要补洞或重建材质。社区对“3D 渲染/深度图先定几何，再由编辑模型补材质”的反馈普遍优于纯提示词，但也反复提到遮挡补洞和材质重建仍会出错。因此这条路径适合把 40°/90°/120° 的大方向和遮挡关系稳定下来，不能宣称任意角度达到真实渲染级精度。

在 16GB 显存机器上，深度模型本身走 CPU，不占用生成模型显存；显存瓶颈仍来自远端或本地的图像生成模型。若使用远端 Nano Banana Pro，节点几何参考不会额外占用本机显存，只会增加参考图上传和上游推理时间。
