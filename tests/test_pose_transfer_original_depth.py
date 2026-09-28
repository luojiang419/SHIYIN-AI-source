import pytest

from canvas_core.ecommerce import build_pose_depth_prompt, STUDIO_REFERENCE_PRESETS
from canvas_core.pose_transfer_geometry import describe_pose_joints


def references():
    return [{"role": role, "url": "/" + role} for role in
            ("source", "control_map", "source_view_1", "source_view_2", "fabric_detail")]


def test_original_depth_prompt_has_real_indices_and_no_case_specific_pose():
    prompt = build_pose_depth_prompt(references())
    assert "Image 1 is the PRIMARY PRODUCT" in prompt
    assert "Image 2 is the ORIGINAL registered person depth" in prompt
    assert "Image 3 is a SAME-PRODUCT" in prompt
    assert "Image 4 is a SAME-PRODUCT" in prompt
    assert "Image 5 is LOCAL SAME-PRODUCT DETAIL" in prompt
    assert "Keep the background and lighting from product Image 1" in prompt
    assert "screen-right leg straight" not in prompt
    assert "1.6 times" not in prompt


def test_explicit_background_and_studio_do_not_compete_with_product_background():
    refs = references() + [{"role": "background", "url": "/background"}]
    prompt = build_pose_depth_prompt(refs, {"instruction": "保留蓝色凉鞋"})
    assert "Image 6 exclusively provides the final background" in prompt
    assert "Keep the background and lighting from product" not in prompt
    assert "USER SUPPLEMENT: 保留蓝色凉鞋" in prompt
    studio = {"studio_reference": STUDIO_REFERENCE_PRESETS[0]["id"]}
    assert "STUDIO REFERENCE LOCK" in build_pose_depth_prompt(references(), studio)
    with pytest.raises(ValueError, match="只能选择一个"):
        build_pose_depth_prompt(refs, studio)


@pytest.mark.parametrize("refs", [references()[1:], references()[:1], references()+[{"role":"pose","url":"/rgb"}]])
def test_invalid_prepared_references_are_not_silently_accepted(refs):
    with pytest.raises(ValueError, match="不能混入动作彩图"):
        build_pose_depth_prompt(refs)


def test_side_pose_keeps_raised_hands_and_rightward_feet_without_case_text():
    points = [[-1,-1] for _ in range(22)]
    scores = [0.] * 22
    for index, point in {4:(60,8),7:(58,9),8:(47,30),11:(59,29),9:(52,58),
                         12:(53,59),10:(34,85),13:(50,87),18:(61,94),21:(44,94)}.items():
        points[index], scores[index] = point, .9
    facts = describe_pose_joints(points,scores,100,100)
    assert len(facts['cues']) == 6
    assert 'ABOVE the hips' in facts['cues'][0]
    assert 'side-on' in facts['cues'][1]
    assert 'SCREEN RIGHT' in facts['cues'][2]
    prompt = build_pose_depth_prompt(references(), {'pose_geometry':facts})
    assert 'MEASURED TARGET POSE' in prompt
    assert 'BOTH feet grounded' in prompt
    assert 'no deeply folded knee' in prompt
    assert 'right_wrist' in facts['joints']
    scores = [0.] * 22
    assert describe_pose_joints(points,scores,100,100)['status'] == 'unavailable'


def test_geometry_does_not_invent_side_pose_for_spread_front_knees():
    points = [[50,50] for _ in range(22)]
    scores = [.9] * 22
    points[9],points[12] = (25,60),(75,60)
    facts=describe_pose_joints(points,scores,100,100)
    assert not any('side-on' in cue for cue in facts['cues'])
