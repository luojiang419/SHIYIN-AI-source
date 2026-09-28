"""从动作关节生成可审计的几何说明，不改变原深度或混入服装外观。"""
from __future__ import annotations
import math


def describe_pose_joints(points, scores, width: int, height: int) -> dict:
    names = {2:'right_shoulder',3:'right_elbow',4:'right_wrist',5:'left_shoulder',
             6:'left_elbow',7:'left_wrist',8:'right_hip',9:'right_knee',10:'right_ankle',
             11:'left_hip',12:'left_knee',13:'left_ankle',18:'left_toe',21:'right_toe'}
    visible = {index:(float(points[index][0])/width,float(points[index][1])/height)
               for index in names if index < len(scores) and float(scores[index]) > .25
               and 0 <= points[index][0] <= width and 0 <= points[index][1] <= height}
    if len(visible) < 6:
        return {'status':'unavailable','reason':'insufficient_visible_joints'}
    cues = []
    hips = [visible[i] for i in (8,11) if i in visible]
    wrists = [visible[i] for i in (4,7) if i in visible]
    if len(hips)==2 and len(wrists)==2 and max(p[1] for p in wrists) < min(p[1] for p in hips)-.08:
        cues.append('Both visible hands/wrists are held ABOVE the hips near the upper torso; do not lower either hand to the thigh or hip.')
    # 只描述可检测的腿部投影，不凭脚向猜测脸的朝向。
    if all(i in visible for i in (8,9,11,12)):
        knee_gap=abs(visible[9][0]-visible[12][0])
        hip_gap=abs(visible[8][0]-visible[11][0])
        if knee_gap < .045 and hip_gap < .17:
            cues.append('The legs project nearly side-on with the knees horizontally overlapping; do not turn the lower body into a broad front-facing stance.')
    directions = [visible[toe][0]-visible[ankle][0] for ankle,toe in ((10,21),(13,18)) if ankle in visible and toe in visible]
    if len(directions)==2 and min(directions) > .045:
        cues.append('Both visible toe directions point toward SCREEN RIGHT relative to their ankles.')
        if any('side-on' in cue for cue in cues):
            cues.append('TARGET SIDE VIEW: orient the person toward SCREEN RIGHT as in the original depth. The front of the body is on the right and the back is on the left. Do not reverse this orientation.')
    elif len(directions)==2 and max(directions) < -.045:
        cues.append('Both visible toe directions point toward SCREEN LEFT relative to their ankles.')
        if any('side-on' in cue for cue in cues):
            cues.append('TARGET SIDE VIEW: orient the person toward SCREEN LEFT as in the original depth. The front of the body is on the left and the back is on the right. Do not reverse this orientation.')
    if 18 in visible and 21 in visible and abs(visible[18][1]-visible[21][1]) < .035:
        cues.append('BOTH toe contact points are at the same ground height. Keep BOTH feet grounded; do not lift a foot, balance on one leg, or raise a knee.')
    bends=[]
    for hip,knee,ankle in ((8,9,10),(11,12,13)):
        if all(i in visible for i in (hip,knee,ankle)):
            h,k,a=(visible[i] for i in (hip,knee,ankle))
            u=((h[0]-k[0])*width,(h[1]-k[1])*height)
            v=((a[0]-k[0])*width,(a[1]-k[1])*height)
            denominator=math.hypot(*u)*math.hypot(*v)
            if denominator:
                bends.append(180-math.degrees(math.acos(max(-1,min(1,(u[0]*v[0]+u[1]*v[1])/denominator)))))
    if len(bends)==2 and max(bends)<65:
        cues.append('The detected legs are standing, with no deeply folded knee. Keep the original mild knee bend and staggered feet; do not create a marching or raised-leg pose.')
    coordinates={names[i]:[round(x,3),round(y,3)] for i,(x,y) in visible.items()}
    return {'status':'succeeded','coordinate_system':'normalized image x-right/y-down; anatomical joint names',
            'joints':coordinates,'cues':cues}
