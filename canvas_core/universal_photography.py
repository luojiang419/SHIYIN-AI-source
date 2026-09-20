"""全能摄影的环境受光与光学景深契约；保真不等于冻结参考图曝光。"""

MATERIAL_IN_SCENE = (
    "MATERIAL EVIDENCE LOCK / INTRINSIC COLOR: owning product references define the exact intrinsic SKU color, "
    "print scale, weave, seams, hardware and material response, not their photographed studio exposure. "
    "Preserve albedo and design while recomputing incident light, shading, specular highlights and subtle local bounce "
    "from the actual environment. Do not paste the reference's flat brightness, white balance or baked-in shadows onto the garment. "
    "Keep neutral midtones recognizably faithful to the SKU; no arbitrary recoloring or overall scene-color wash. "
    "Preserve actual thread direction, weave scale, seam puckering, print alignment and material thickness at the subject focus plane. "
    "Texture follows the garment geometry and optical focus; do not replace fabric with sharpening noise."
)


def build_universal_photography_contract(style: str, scene_index: int | None = None) -> str:
    scene = f"场景图{scene_index}" if scene_index else "所选摄影棚或已确定的实际环境"
    optics = (
        "标准产品图使用自然的中长焦人像透视，约 65–85mm、f/4–f/5.6 的视觉效果。"
        "将脸与主要服装衣片安排在可清晰覆盖的主体焦平面内，产品轮廓、腰头和织纹清楚；"
        "通过人物与远处背景的真实距离形成适度光学虚化，不能为展示产品把整片背景也变成实焦。"
        if style == "standard_product" else
        "Lookbook 使用有意图的 50–85mm 人像透视和约 f/2.8–f/4 的光学层次，按场景空间选择机位，"
        "让姿态、视线、环境中的动作和前后景形成张力。脸与关键商品结构保持可读，"
        "远处建筑、车辆和树木渐进失焦；创意不能靠把衣服本身模糊掉。"
    )
    return "\n".join([
        "【同一现场、同一次曝光：环境先于人物照明】",
        f"把{scene}当作真实三维拍摄现场，不是贴在人物背后的平面背景。先读可见天空、遮挡、地面、墙面与已有阴影，确定人物具体站在哪里、处于日照还是阴影，以及相机的位置。保留地点的建筑与物体身份，但不要继承场景参考的全实焦或原取景框。",
        "人物身份不是源照片曝光：保留同一个人的五官、肤色底色、发型和身体比例，删除模特参考原有的棚拍补光、脸部亮度、轮廓光和原背景溢色。按这个位置重新计算脸、鼻影、眼窝、下颌、颈部、手臂、头发和全部衣物的受光，不能只换背景或只给衣服调色。",
        "从现场读主光方向、大小、软硬和亮暗比；有直射光证据才使用对应方向的太阳光，阴影区或阴天使用开阔天空的柔光。没有证据不增加金色轮廓光、正面柔光箱、闪光灯或电影光束。保留有依据的脸侧阴影与身体转折，不做全脸均匀美颜补光。",
        "地面和邻近墙面向下颌、手臂暗面及裤腿产生克制的真实反射光，天空向朝上的表面提供环境光；这是局部受光变化，不是把整件商品染色。皮肤、棉布、金属和透明鞋面分别响应同一光场，亮部不过度抛光，皮肤保留自然纹理。",
        "脚底或鞋跟必须落在同一真实地面上：匹配碎石/地板坡度、接触点的小遮挡与贴地暗部，投影方向和软硬与现场一致。禁止悬浮、脚下统一椭圆影、抠图白边或一圈无来源的亮边。人物尺度、地平线、透视缩短和场景物体距离必须属于同一相机。",
        "【真实景深，不用全画面锐利充当高质量】",
        optics,
        "建立近景、主体、中景、远景四层：主体焦平面自然清晰，同距离地面相应清晰；越远离焦平面的前景与背景越柔和。远处窗格和树叶不能与衣服织纹同样锐利。保留背景可识别的轮廓与色块，减少远景微对比，让它退到人物身后。",
        "虚化来自距离、焦平面和镜头，不是在人物边缘画一个清晰蒙版再对背景统一高斯模糊。发丝、透明鞋带和轮廓过渡自然，衣服与身体同属一个光学成像系统。禁止焦点堆栈、手机式全距离锐化、HDR 提亮所有阴影、人物贴纸感、摄影棚人像加旅游背景的合成观感。",
        "商品保真锁定固有色、设计与材质；场景决定它们如何被照亮和被镜头成像。",
    ])
