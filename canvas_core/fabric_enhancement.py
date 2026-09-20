"""从参考布面提取微观纹理；定位不可靠时保留生成原图。"""
from pathlib import Path
import threading

import cv2
import numpy as np
from PIL import Image, ImageOps

_LOCK = threading.Lock()
MAX_PIXELS = 40_000_000


def read_rgb(path):
    with Image.open(path) as source:
        if source.width * source.height > MAX_PIXELS:
            raise ValueError('image_too_large')
        return np.asarray(ImageOps.exif_transpose(source).convert('RGB')).copy()


def material_patch(reference):
    h, w = reference.shape[:2]
    if min(h, w) < 320:
        return None
    small = cv2.resize(reference, (min(w, 384), min(h, 384)), interpolation=cv2.INTER_AREA)
    lab = cv2.cvtColor(small, cv2.COLOR_RGB2LAB)
    cv2.setRNGSeed(0)
    _, labels, centers = cv2.kmeans(lab.reshape(-1, 3).astype('float32'), 5, None,
        (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 25, .2), 2, cv2.KMEANS_PP_CENTERS)
    fractions = np.bincount(labels[:, 0], minlength=5) / labels.size
    rgb = cv2.cvtColor(centers.astype('uint8')[None], cv2.COLOR_LAB2RGB)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)[0]
    eligible = [i for i in range(5) if fractions[i] > .08 and hsv[i, 1] > 42 and hsv[i, 2] < 230]
    if not eligible:
        return None
    center = centers[max(eligible, key=lambda i: fractions[i])]
    side = min(384, min(h, w))
    best = None
    for y in range(0, h-side+1, max(64, side//2)):
        for x in range(0, w-side+1, max(64, side//2)):
            patch = reference[y:y+side, x:x+side]
            colors = cv2.cvtColor(patch, cv2.COLOR_RGB2LAB).astype('float32')
            coverage = np.mean(np.linalg.norm(colors-center, axis=2) < 42)
            if coverage < .90:
                continue
            gray = cv2.cvtColor(patch, cv2.COLOR_RGB2GRAY).astype('float32')
            high = gray-cv2.GaussianBlur(gray, (0, 0), 4)
            strength = np.std(np.clip(high, -35, 35))
            if not 4 < strength < 24:
                continue
            # 排除没有方向组织的噪点/平滑材料；不凭此声称适配所有面料。
            gx, gy = np.gradient(cv2.GaussianBlur(gray, (0, 0), .5))
            xx, yy, xy = np.mean(gx*gx), np.mean(gy*gy), np.mean(gx*gy)
            coherence = np.sqrt((xx-yy)**2+4*xy**2)/(xx+yy+1e-6)
            if coherence < .20:
                continue
            score = coverage*30+strength*.25-cv2.GaussianBlur(gray, (0, 0), 12).std()*.8
            if best is None or score > best[0]:
                best = (score, patch.copy(), np.median(colors.reshape(-1, 3), axis=0))
    return None if best is None else best[1:]


def garment_mask(base, color, foreground):
    h, w = base.shape[:2]
    lab = cv2.cvtColor(base, cv2.COLOR_RGB2LAB).astype('float32')
    delta = lab-color
    delta[:, :, 0] *= .4
    distance = np.linalg.norm(delta, axis=2)
    candidate = ((distance < 19) & (lab[:, :, 0] < color[0]+26)).astype('uint8')*255
    if foreground is None:
        # 常规电商页面没有深度控制图。只在颜色候选本身形成一个内嵌、足够大的
        # 衣片时继续，宁可跳过也不要触及整张背景或画面边缘。
        candidate = cv2.morphologyEx(candidate, cv2.MORPH_CLOSE, np.ones((9, 9), 'uint8'))
        opening = max(9, int(min(h, w)*.027) | 1)
        candidate = cv2.morphologyEx(candidate, cv2.MORPH_OPEN,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (opening, opening)))
        n, labels, stats, _ = cv2.connectedComponentsWithStats(candidate, 8)
        eligible = [i for i in range(1, n) if h*w*.025 < stats[i, 4] < h*w*.5]
        if not eligible:
            return None
        index = max(eligible, key=lambda i: stats[i, 4])
        x, y, bw, bh, _ = stats[index]
        if x < 3 or y < 3 or x+bw >= w-3 or y+bh >= h-3:
            return None
        return (labels == index).astype('uint8')*255
    person = cv2.resize(foreground, (w, h), interpolation=cv2.INTER_LINEAR) > 12
    counts = np.sum((candidate > 0) & person, axis=1).astype('float32')
    counts = cv2.blur(counts[:, None], (1, max(15, h//80)))[:, 0]
    n, _, stats, _ = cv2.connectedComponentsWithStats((counts > w*.11).astype('uint8')[:, None], 8)
    if n < 2:
        return None
    band = max(range(1, n), key=lambda i: stats[i, cv2.CC_STAT_AREA])
    top, length = int(stats[band, 1]), int(stats[band, 3])
    if length < h*.15:
        return None
    pad = max(8, h//15)
    candidate[:max(0, top-pad)] = 0
    candidate[min(h, top+length+pad):] = 0
    radius = max(3, int(min(h, w)*.025))
    rough = cv2.dilate(person.astype('uint8'), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius*2+1,)*2))
    candidate[rough == 0] = 0
    candidate = cv2.morphologyEx(candidate, cv2.MORPH_CLOSE, np.ones((9, 9), 'uint8'))
    # 去除与衣片仅通过细窄阴影相连的手臂、手指和鞋带。
    opening = max(9, int(min(h, w)*.027) | 1)
    candidate = cv2.morphologyEx(candidate, cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (opening, opening)))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(candidate, 8)
    eligible = [i for i in range(1, n) if stats[i, 4] > h*w*.025]
    if not eligible:
        return None
    index = max(eligible, key=lambda i: stats[i, 4])
    x, y, bw, bh, area = stats[index]
    if x < 3 or y < 3 or x+bw >= w-3 or y+bh >= h-3 or area > h*w*.5:
        return None
    mask = (labels == index).astype('uint8')*255
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(mask)
    cv2.drawContours(filled, contours, -1, 255, -1)
    if np.count_nonzero(mask)/max(1, np.count_nonzero(filled)) < .7:
        return None
    filled[(distance > 30) | (lab[:, :, 0] > color[0]+35) | (rough == 0)] = 0
    return filled


def refine_garment_boundary(base, mask):
    """按生成图自身的颜色边界收紧衣片，禁止从粗掩膜向皮肤扩张。"""
    h, w = mask.shape
    scale = min(1., 1200 / max(h, w))
    size = (max(1, round(w*scale)), max(1, round(h*scale)))
    small = cv2.resize(base, size, interpolation=cv2.INTER_AREA)
    coarse = cv2.resize(mask, size, interpolation=cv2.INTER_NEAREST)
    radius = max(3, round(min(size)*.025))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius*2+1,)*2)
    core = cv2.erode(coarse, kernel) > 0
    outside = cv2.dilate(coarse, kernel) == 0
    if not np.any(core) or not np.any(outside):
        return None
    labels = np.where(coarse > 0, cv2.GC_PR_FGD, cv2.GC_PR_BGD).astype('uint8')
    labels[core], labels[outside] = cv2.GC_FGD, cv2.GC_BGD
    # 阴影皮肤可与棕布亮度相同，但色度常偏离衣片内部。仅在不确定边缘
    # 要求色度受内部像素支持；不用肤色常量，避免把不同肤色/服装写死。
    chroma = cv2.cvtColor(small, cv2.COLOR_RGB2LAB)[:, :, 1:].astype('float32')
    low, high = np.percentile(chroma[core], [1, 99], axis=0)
    supported = np.all((chroma >= low-2) & (chroma <= high+2), axis=2)
    labels[(~core) & (~supported)] = cv2.GC_BGD
    try:
        cv2.setRNGSeed(0)
        cv2.grabCut(small, labels, None, np.zeros((1, 65)), np.zeros((1, 65)),
                    4, cv2.GC_INIT_WITH_MASK)
    except cv2.error:
        return None
    refined = np.isin(labels, [cv2.GC_FGD, cv2.GC_PR_FGD]).astype('uint8')*255
    # 留出窄小保护边：裤脚/袖口的抗锯齿和阴影不能承担织纹来源。
    refined = cv2.erode(refined, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    refined = cv2.resize(refined, (w, h), interpolation=cv2.INTER_LINEAR)
    refined = ((refined == 255) & (mask > 0)).astype('uint8')*255
    if np.count_nonzero(refined) < np.count_nonzero(mask)*.65:
        return None
    return refined


def enhance_fabric_image(generated, detail, output, control=None):
    # 限制高分辨率数组并发，批量任务不同时占用数 GB 内存。
    with _LOCK:
        base, reference = read_rgb(generated), read_rgb(detail)
        material = material_patch(reference)
        if material is None:
            return {'status': 'skipped', 'reason': 'no_reliable_woven_sample'}
        foreground = None
        if control:
            with Image.open(control) as im:
                foreground = np.asarray(im.convert('L'))
        patch, color = material
        mask = garment_mask(base, color, foreground)
        if mask is None:
            return {'status': 'skipped', 'reason': 'garment_mask_ambiguous'}
        mask = refine_garment_boundary(base, mask)
        if mask is None:
            return {'status': 'skipped', 'reason': 'garment_boundary_ambiguous'}
        h, w = base.shape[:2]
        scale = max(.5, min(1., max(h, w)/4800*.75))
        patch = cv2.resize(patch, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(patch, cv2.COLOR_RGB2GRAY).astype('float32')
        weave = gray-cv2.GaussianBlur(gray, (0, 0), 4)
        weave -= weave.mean()
        ph, pw = weave.shape
        tiled = np.tile(weave, ((h+ph-1)//ph, (w+pw-1)//pw))[:h, :w]
        shifted = np.roll(tiled, (ph//2, pw//2), axis=(0, 1))
        yy, xx = np.arange(h)%ph, np.arange(w)%pw
        weight = np.minimum(np.minimum(yy, ph-yy)[:, None], np.minimum(xx, pw-xx)[None, :])
        weight = np.clip(weight.astype('float32')/24, 0, 1)
        texture = np.clip((tiled*weight+shifted*(1-weight))*.5, -12, 12)
        alpha = cv2.GaussianBlur(mask.astype('float32')/255, (0, 0), 1.5)
        alpha[mask == 0] = 0
        result = np.clip(base.astype('float32')+texture[:, :, None]*alpha[:, :, None], 0, 255).astype('uint8')
        destination = Path(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(result).save(destination, 'PNG')
        return {'status': 'applied', 'masked_pixels': int(np.count_nonzero(mask)), 'scale': scale,
                'boundary_guard': 'image_edges_inset_v1'}
