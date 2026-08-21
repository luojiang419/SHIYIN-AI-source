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

    def test_default_provider_is_exposed_from_api_configuration(self):
        assert '"primary_provider_id": get_primary_provider_id(providers)' in self.backend
        assert "managedProviderId = cfg.primary_provider_id" in self.javascript
        assert "provider.primary === true" in self.javascript
        assert "primary:item.primary === true" in self.api_settings


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
