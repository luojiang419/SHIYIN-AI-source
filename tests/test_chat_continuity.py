import unittest

import main


class ChatContinuityTests(unittest.TestCase):
    def test_generated_assets_keep_stable_identity_and_parent_references(self):
        refs = [{
            "asset_id": "horse-1",
            "url": "/assets/output/horse.png",
            "name": "马",
            "role": "subject",
        }]
        assets = main.chat_generated_assets(
            ["/assets/output/cowgirl.png", "/assets/output/cowgirl-2.png"],
            "生成女牛仔",
            message_id="message-1",
            provider="comfly",
            model="gpt-image-2",
            references=refs,
        )
        self.assertEqual(len(assets), 2)
        self.assertTrue(assets[0]["asset_id"].startswith("chat_asset_"))
        self.assertNotEqual(assets[0]["asset_id"], assets[1]["asset_id"])
        self.assertEqual(assets[0]["message_id"], "message-1")
        self.assertEqual(assets[0]["image_index"], 0)
        self.assertEqual(assets[1]["image_index"], 1)
        self.assertEqual(assets[0]["parent_references"][0]["asset_id"], "horse-1")

    def test_latest_refs_reads_all_assets_from_latest_batch_when_requested(self):
        conversation = {
            "messages": [{
                "role": "assistant",
                "type": "image",
                "content": "生成一批马",
                "image_url": "/assets/output/horse-1.png",
                "image_urls": ["/assets/output/horse-1.png", "/assets/output/horse-2.png"],
                "generated_assets": [
                    {"asset_id": "horse-1", "url": "/assets/output/horse-1.png", "name": "马 1"},
                    {"asset_id": "horse-2", "url": "/assets/output/horse-2.png", "name": "马 2"},
                ],
            }]
        }
        refs = main.latest_chat_image_refs(conversation, limit=2)
        self.assertEqual([item["asset_id"] for item in refs], ["horse-1", "horse-2"])
        self.assertEqual([item["url"] for item in refs], [
            "/assets/output/horse-1.png",
            "/assets/output/horse-2.png",
        ])

    def test_legacy_image_messages_remain_readable(self):
        conversation = {
            "messages": [{
                "role": "assistant",
                "type": "image",
                "content": "旧版图片",
                "image_url": "/output/legacy.png",
            }]
        }
        refs = main.latest_chat_image_refs(conversation)
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["url"], "/output/legacy.png")
        self.assertEqual(refs[0]["name"], "旧版图片")


if __name__ == "__main__":
    unittest.main()
