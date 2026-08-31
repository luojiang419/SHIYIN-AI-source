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

    def test_delete_one_image_keeps_message_and_other_assets(self):
        conversation = {
            "messages": [{
                "id": "message-1",
                "role": "assistant",
                "type": "image",
                "image_url": "/output/horse-1.png",
                "image_urls": ["/output/horse-1.png", "/output/horse-2.png"],
                "generated_assets": [
                    {"asset_id": "horse-1", "url": "/output/horse-1.png"},
                    {"asset_id": "horse-2", "url": "/output/horse-2.png"},
                ],
            }]
        }
        message = main.delete_chat_message_asset(conversation, "message-1", asset_id="horse-1")
        self.assertEqual(message["image_url"], "/output/horse-2.png")
        self.assertEqual(message["image_urls"], ["/output/horse-2.png"])
        self.assertEqual([item["asset_id"] for item in message["generated_assets"]], ["horse-2"])
        self.assertNotIn("deleted_at", message)

    def test_delete_last_image_soft_deletes_message_without_removing_file(self):
        conversation = {
            "messages": [{
                "id": "message-2",
                "role": "assistant",
                "type": "image",
                "image_url": "/output/cowgirl.png",
                "image_urls": ["/output/cowgirl.png"],
                "generated_assets": [{"asset_id": "cowgirl-1", "url": "/output/cowgirl.png"}],
            }]
        }
        message = main.delete_chat_message_asset(conversation, "message-2", asset_id="cowgirl-1")
        self.assertTrue(message["deleted_at"])
        self.assertEqual(message["image_url"], "")
        self.assertEqual(message["image_urls"], [])
        self.assertEqual(message["deleted_assets"][0]["url"], "/output/cowgirl.png")


if __name__ == "__main__":
    unittest.main()
