import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class TestCanvasStoryboardTransformPanel:
    @classmethod
    def setup_class(cls):
        cls.html = (ROOT / "static" / "canvas.html").read_text(encoding="utf-8")
        cls.javascript = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
        cls.api_settings = (ROOT / "static" / "js" / "api-settings.js").read_text(encoding="utf-8")
        cls.backend = (ROOT / "main.py").read_text(encoding="utf-8")

    def test_group_transform_actions_open_parameter_panel(self):
        assert 'id="storyboardTransformModal"' in self.html
        assert 'id="storyboardTransformProvider"' in self.html
        assert 'id="storyboardTransformModel"' in self.html
        assert "function openStoryboardTransformPanel(operation, groupId)" in self.javascript
        assert "openStoryboardTransformPanel(action, target?.nodeId)" in self.javascript

    def test_transform_uses_selected_panel_parameters(self):
        transform = re.search(
            r"async function transformStoryboardFrame\(frame, operation, providerId, model, index, options=\{\}\)\{(?P<body>.*?)\n\}",
            self.javascript,
            re.DOTALL,
        )
        assert transform
        body = transform.group("body")
        assert "options.ratio" in body
        assert "options.resolution" in body
        assert "quality," in body
        assert "storyboardTransformSize(frame, model, ratio, resolution)" in body

        run = re.search(
            r"async function runGroupTransformation\(operation, groupId, options=\{\}\)\{(?P<body>.*?)\n\}",
            self.javascript,
            re.DOTALL,
        )
        assert run
        run_body = run.group("body")
        assert "defaultImageGenerationSelection()" in run_body
        assert "options.providerId" in run_body
        assert "options.model" in run_body
        assert "imageApiProviders()[0]" not in run_body

    def test_flux2_klein_4b_uses_tested_prompt_and_source_auto_size(self):
        assert "FLUX2_KLEIN_4B_LINE_ART_PROMPT" in self.javascript
        assert "faithful style transfer of the same frame" in self.javascript
        assert "function isFlux2Klein4BModel(model='')" in self.javascript
        assert "if(isFlux2Klein4BModel(model)) return 'auto';" in self.javascript
        assert "transformationPrompt(operation, model)" in self.javascript

    def test_line_art_defaults_to_source_ratio_without_changing_expand_canvas(self):
        assert '<option value="source">跟随原图（推荐）</option>' in self.html
        assert '<option value="3:2">3:2 横屏</option>' in self.html
        assert '<option value="2:3">2:3 竖屏</option>' in self.html
        assert "operation === 'line-art' ? 'source' : '16:9'" in self.javascript
        assert "['source','16:9','1:1','9:16','3:2','2:3']" in self.javascript
        assert "natural_w:Number(n.natural_w || n.width || 0)" in self.javascript

    def test_default_provider_is_exposed_from_api_configuration(self):
        assert '"primary_provider_id": get_primary_provider_id(providers)' in self.backend
        assert "managedProviderId = cfg.primary_provider_id" in self.javascript
        assert "provider.primary === true" in self.javascript
        assert "primary:item.primary === true" in self.api_settings


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
