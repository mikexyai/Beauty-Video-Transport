import unittest
from unittest.mock import patch

from scripts.ai_beauty.collect_urls import extract_aweme_id
from scripts.ai_beauty.media import has_video_stream, duration_seconds, dimensions
from pathlib import Path

from scripts.ai_beauty.download_candidate import build_ytdlp_args, pick_best_play_url, build_cdp_detail_expression, summarize_douyin_video_variants
from scripts.bilibili_download_best import build_bilibili_ytdlp_args
from scripts.ai_beauty.refresh_douyin_cookies import _sign_with_node
from scripts.ai_beauty.record_screening import build_screening_insert_params, validate_screening
from scripts.ai_beauty.search_douyin import build_search_query, extract_aweme_candidates, filter_storeable_candidates
from scripts.ai_beauty.rank_candidates import score_candidate, rank_candidates
from scripts.ai_beauty.state import (
    ACTIVE_STATUSES,
    ARCHIVE_PRUNED_STATUS,
    ARCHIVED_STATUS,
    BATCH_SELECTED_STATUS,
    FAILED_STATUS,
    NEW_STATUS,
    PROCESSABLE_STATUSES,
    SCREENED_OUT_STATUS,
    TERMINAL_STATUSES,
    UPLOADED_STATUS,
    assert_transition_allowed,
    is_active_status,
    is_terminal_status,
)
from scripts.ai_beauty.process_top_candidates import select_top_candidates, archive_non_top_candidates
from scripts.ai_beauty.upload_ai_beauty import build_upload_args, parse_upload_json
from scripts.ai_beauty.report_status import latest_uploads, summarize_local_artifact_state
from scripts.ai_beauty.scheduled_run import build_search_plan, parse_keywords
from scripts.ai_beauty.process_selected import build_screening_template, select_batch_rows, should_cleanup_after_decision
from scripts.ai_beauty.verify_uploads import summarize_video_status
from scripts.ai_beauty.repositories.candidates import CandidateRepository
from scripts.ai_beauty.normalize_screening_json import extract_json_object, normalize_screening
from scripts.ai_beauty.migrate_candidate_status_constraint import build_candidate_status_constraint_sql, invalid_statuses
from scripts.ai_beauty.repositories.run_logs import RunLogRepository, build_run_summary
from scripts.youtube_profile_guard import validate_channel_identity
from scripts.ai_beauty.operator import operator_should_continue, summarize_operator_iteration
from scripts.ai_beauty.duplicate_detection import assess_text_duplicate_risk, normalize_duplicate_text, hamming_distance
from scripts.bilibili_pipeline import decide_bilibili_candidate_action, route_bilibili_upload, build_bilibili_pipeline_plan
from scripts.ai_beauty.fetch_metrics import parse_video_metric_item, build_metric_upsert_params
from scripts.ai_beauty.update_strategy import build_strategy_recommendations


class AiBeautyCoreTests(unittest.TestCase):
    def test_extract_aweme_id_from_douyin_video_url(self):
        self.assertEqual(
            extract_aweme_id("https://www.douyin.com/video/7654321098765432101"),
            "7654321098765432101",
        )

    def test_extract_aweme_id_from_modal_url(self):
        self.assertEqual(
            extract_aweme_id("https://www.douyin.com/user/self?modal_id=7654321098765432101"),
            "7654321098765432101",
        )

    def test_media_helpers_parse_video_stream(self):
        probe = {
            "streams": [
                {"codec_type": "audio"},
                {"codec_type": "video", "width": 1080, "height": 1920, "duration": "12.5"},
            ],
            "format": {"duration": "12.6"},
        }
        self.assertTrue(has_video_stream(probe))
        self.assertEqual(dimensions(probe), (1080, 1920))
        self.assertAlmostEqual(duration_seconds(probe), 12.5)

    def test_screening_allows_suggestive_and_dance_labels_when_approved(self):
        data = {
            "is_beauty_content": True,
            "suitable_for_ai_beauty": True,
            "visible_minor_risk": False,
            "sensuality_level": "high",
            "explicitness_level": "medium",
            "content_type": ["beauty", "dance", "cosplay"],
            "decision": "approved",
            "recommended_title": "Glamorous Beauty Short",
            "recommended_tags": ["beauty", "glamour", "shorts"],
            "selection_reason": "Strong visual appeal.",
        }
        normalized = validate_screening(data)
        self.assertEqual(normalized["decision"], "approved")
        self.assertIn("dance", normalized["content_type"])

    def test_screening_rejects_approved_with_more_than_five_tags(self):
        data = {
            "decision": "approved",
            "recommended_title": "Beauty Short",
            "recommended_tags": ["1", "2", "3", "4", "5", "6"],
        }
        with self.assertRaises(ValueError):
            validate_screening(data)

    def test_build_screening_insert_params_preserves_decision_without_status_update(self):
        data = {
            "decision": "review",
            "recommended_tags": ["beauty"],
            "content_type": "beauty",
            "visual_style": "portrait",
        }
        params = build_screening_insert_params("aweme123", data, model_name="vision-test")
        self.assertEqual(params["aweme_id"], "aweme123")
        self.assertEqual(params["decision"], "review")
        self.assertEqual(params["content_type"], ["beauty"])
        self.assertNotIn("candidate_status", params)
        self.assertNotIn("status", params)

    def test_record_screening_does_not_update_candidate_status(self):
        class FakeConn:
            def __init__(self):
                self.queries = []
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def execute(self, query, params=None):
                self.queries.append(str(query))
                class Result:
                    def fetchone(self_inner):
                        return [123]
                return Result()
            def commit(self):
                pass
        fake = FakeConn()
        with patch("scripts.ai_beauty.record_screening.connect", return_value=fake):
            screening_id = __import__("scripts.ai_beauty.record_screening", fromlist=["record_screening"]).record_screening(
                "aweme123",
                {"decision": "review", "recommended_tags": ["beauty"]},
            )
        self.assertEqual(screening_id, 123)
        joined = "\n".join(fake.queries).lower()
        self.assertIn("insert into beauty.ai_beauty_screenings", joined)
        self.assertNotIn("update beauty.ai_beauty_candidates", joined)

    def test_extract_json_object_handles_markdown_fenced_json(self):
        raw = 'Analysis:\n```json\n{"decision":"approved","recommended_title":"T","recommended_tags":["beauty"]}\n```'
        self.assertEqual(extract_json_object(raw)["decision"], "approved")

    def test_normalize_screening_downgrades_minor_risk_and_caps_tags(self):
        normalized = normalize_screening(
            {
                "decision": "approved",
                "title": "Cute Beauty",
                "tags": ["1", "2", "3", "4", "5", "6"],
                "minor_risk": True,
                "content_type": "beauty",
                "visual_style": "portrait",
            },
            contact_sheet_path="analysis/x/contact_sheet.jpg",
        )
        self.assertEqual(normalized["decision"], "review")
        self.assertTrue(normalized["visible_minor_risk"])
        self.assertEqual(len(normalized["recommended_tags"]), 5)
        self.assertEqual(normalized["recommended_title"], "Cute Beauty")
        self.assertEqual(normalized["contact_sheet_path"], "analysis/x/contact_sheet.jpg")

    def test_normalize_screening_detects_long_compilation(self):
        normalized = normalize_screening(
            {
                "decision": "approved",
                "recommended_title": "Top Beauty List",
                "recommended_tags": ["beauty"],
                "duration_seconds": 224.8,
                "content_type": ["beauty", "ranking compilation"],
            },
            contact_sheet_path="analysis/x/contact_sheet.jpg",
        )
        self.assertEqual(normalized["decision"], "skipped")
        self.assertIn("compilation", normalized["skip_reason"].lower())

    def test_upload_args_force_default_profile_public_empty_description(self):
        args = build_upload_args(
            file_path="downloads/douyin_ai_beauty/765.mp4",
            title="Beauty Short",
            tags=["beauty", "shorts"],
        )
        joined = " ".join(args)
        self.assertIn("--profile", args)
        self.assertIn("default", args)
        self.assertIn("--privacyStatus", args)
        self.assertIn("public", args)
        self.assertIn("--description", args)
        self.assertIn("", args)
        self.assertNotIn("channelCos", joined)
        self.assertNotIn("channelDance", joined)

    def test_parse_upload_json_returns_last_json_object_after_progress_lines(self):
        output = '{"progress": 50}\n{"status":"uploaded","video_id":"abc123","url":"https://www.youtube.com/watch?v=abc123"}\n'
        parsed = parse_upload_json(output)
        self.assertEqual(parsed["status"], "uploaded")
        self.assertEqual(parsed["video_id"], "abc123")

    def test_parse_upload_json_handles_nested_dry_run_metadata(self):
        output = '''noise
{
  "mode": "dry-run",
  "metadata": {
    "snippet": {"title": "Beauty", "tags": ["beauty"]},
    "status": {"privacyStatus": "public"}
  }
}
'''
        parsed = parse_upload_json(output)
        self.assertEqual(parsed["mode"], "dry-run")
        self.assertEqual(parsed["metadata"]["status"]["privacyStatus"], "public")

    def test_ytdlp_args_include_ai_beauty_cookie_file_when_present(self):
        args = build_ytdlp_args(
            "https://www.douyin.com/video/7654321098765432101",
            Path("downloads/douyin_ai_beauty/7654321098765432101.mp4"),
            cookies_path=Path("config/douyin_ai_beauty_cookies.txt"),
            cookies_exist=True,
        )
        self.assertIn("--cookies", args)
        self.assertIn(str(Path("config/douyin_ai_beauty_cookies.txt")), args)

    def test_pick_best_play_url_prefers_direct_mp4_over_aweme_play_endpoint(self):
        detail = {
            "aweme_detail": {
                "video": {
                    "play_addr": {
                        "url_list": [
                            "https://www.douyin.com/aweme/v1/play/?video_id=x&is_play_url=1",
                            "https://v26-web.douyinvod.com/path/video.mp4?mime_type=video_mp4&br=2000",
                        ]
                    }
                }
            }
        }
        self.assertEqual(
            pick_best_play_url(detail),
            "https://v26-web.douyinvod.com/path/video.mp4?mime_type=video_mp4&br=2000",
        )

    def test_pick_best_play_url_prefers_highest_douyin_bit_rate_variant(self):
        detail = {
            "aweme_detail": {
                "video": {
                    "play_addr": {"url_list": ["https://v.douyinvod.com/default_720.mp4"], "width": 720, "height": 1280},
                    "bit_rate": [
                        {"bit_rate": 1000, "play_addr": {"url_list": ["https://v.douyinvod.com/720.mp4"], "width": 720, "height": 1280}},
                        {"bit_rate": 1800, "play_addr": {"url_list": ["https://v.douyinvod.com/1080.mp4"], "width": 1080, "height": 1920}},
                    ],
                }
            }
        }
        self.assertEqual(pick_best_play_url(detail), "https://v.douyinvod.com/1080.mp4")

    def test_summarize_douyin_video_variants_reports_selected_top_quality(self):
        detail = {"aweme_detail": {"video": {"bit_rate": [{"bit_rate": 1, "gear_name": "low", "play_addr": {"width": 720, "height": 1280, "url_list": ["u"]}}]}}}
        summary = summarize_douyin_video_variants(detail, "u")
        self.assertEqual(summary["selected"]["bit_rate"], 1)
        self.assertEqual(summary["variant_count"], 1)

    def test_bilibili_ytdlp_args_request_best_video_and_audio(self):
        args = build_bilibili_ytdlp_args("BV123", Path("downloads/bilibili/BV123.mp4"), cookies_path=Path("cookies.txt"))
        joined = " ".join(args)
        self.assertIn("-f", args)
        self.assertIn("bestvideo", joined)
        self.assertIn("bestaudio", joined)
        self.assertIn("--format-sort", args)
        self.assertIn("res", joined)

    def test_build_cdp_detail_expression_uses_credentials_include_and_pauses_videos(self):
        expression = build_cdp_detail_expression("7654321098765432101")
        self.assertIn("credentials:'include'", expression)
        self.assertIn("aweme/detail", expression)
        self.assertIn("7654321098765432101", expression)
        self.assertIn("pause", expression)

    def test_douyin_acrawler_signature_from_saved_challenge_js(self):
        challenge = Path("analysis/douyin_ai_beauty/douyin_acrawler_challenge.js")
        if not challenge.exists():
            self.skipTest("Douyin challenge JS fixture not present")
        sig = _sign_with_node(
            challenge,
            "06a41496d00b60891e80e",
            "https://www.douyin.com/video/7641955872135475621",
        )
        self.assertTrue(sig.startswith("_02B4Z6wo"))

    def test_build_search_query_contains_required_web_params(self):
        query = build_search_query(keyword="美女", offset=10, count=20)
        self.assertEqual(query["keyword"], "美女")
        self.assertEqual(query["offset"], "10")
        self.assertEqual(query["count"], "20")
        self.assertEqual(query["search_channel"], "aweme_video_web")
        self.assertEqual(query["device_platform"], "webapp")
        self.assertEqual(query["aid"], "6383")

    def test_extract_aweme_candidates_from_general_search_response(self):
        payload = {
            "data": [
                {
                    "type": 1,
                    "aweme_info": {
                        "aweme_id": "7407402364249935143",
                        "desc": "秋天就要跳so Crazy！ #甜妹",
                        "duration": 18000,
                        "author": {"uid": "u1", "nickname": "作者"},
                        "statistics": {"digg_count": 10, "comment_count": 2},
                        "video": {"width": 720, "height": 1280},
                        "text_extra": [{"hashtag_name": "甜妹"}],
                    },
                }
            ],
            "has_more": 1,
            "cursor": 10,
        }
        candidates = extract_aweme_candidates(payload)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["aweme_id"], "7407402364249935143")
        self.assertEqual(candidates[0]["author_name"], "作者")
        self.assertIn("甜妹", candidates[0]["hashtags"])

    def test_filter_storeable_candidates_excludes_screened_out_and_uploaded_ids(self):
        candidates = [{"aweme_id": "keep"}, {"aweme_id": "screened"}, {"aweme_id": "uploaded"}]
        filtered = filter_storeable_candidates(candidates, excluded_aweme_ids={"screened", "uploaded"})
        self.assertEqual(filtered, [{"aweme_id": "keep"}])

    def test_candidate_repository_builds_terminal_exclusion_filter(self):
        repo = CandidateRepository(connect_fn=None)
        candidates = [{"aweme_id": "keep"}, {"aweme_id": "screened"}, {"aweme_id": "uploaded"}]
        filtered = repo.filter_storeable_candidates(candidates, excluded_aweme_ids={"screened", "uploaded"})
        self.assertEqual(filtered, [{"aweme_id": "keep"}])

    def test_candidate_repository_transition_methods_use_central_state_values(self):
        class FakeResult:
            description = []
            def fetchall(self):
                return []
            def fetchone(self):
                return None
        class FakeConn:
            def __init__(self):
                self.calls = []
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def execute(self, query, params=None):
                self.calls.append((str(query), params))
                return FakeResult()
            def commit(self):
                pass
        fake = FakeConn()
        repo = CandidateRepository(connect_fn=lambda: fake)
        repo.mark_status("a1", SCREENED_OUT_STATUS, "screened")
        repo.mark_status("a2", BATCH_SELECTED_STATUS)
        self.assertEqual(fake.calls[0][1]["status"], SCREENED_OUT_STATUS)
        self.assertEqual(fake.calls[1][1]["status"], BATCH_SELECTED_STATUS)

    def test_score_candidate_prioritizes_engagement_vertical_and_beauty_keywords(self):
        high = {
            "aweme_id": "1",
            "caption": "氛围感美女 黑长直 原相机",
            "hashtags": ["美女", "甜妹"],
            "width": 720,
            "height": 1280,
            "source_stats": {"digg_count": 1000000, "share_count": 400000, "collect_count": 80000, "comment_count": 20000},
        }
        low = {
            "aweme_id": "2",
            "caption": "普通日常",
            "hashtags": [],
            "width": 1280,
            "height": 720,
            "source_stats": {"digg_count": 500, "share_count": 10, "collect_count": 5, "comment_count": 1},
        }
        self.assertGreater(score_candidate(high), score_candidate(low) + 50)

    def test_rank_candidates_returns_descending_scores_without_mutating_input(self):
        original = [
            {"aweme_id": "low", "caption": "普通", "source_stats": {"digg_count": 1}},
            {"aweme_id": "high", "caption": "美女 甜妹", "height": 1920, "width": 1080, "source_stats": {"digg_count": 100000}},
        ]
        ranked = rank_candidates(original)
        self.assertEqual([item["aweme_id"] for item in ranked], ["high", "low"])
        self.assertIn("priority_score", ranked[0])
        self.assertNotIn("priority_score", original[0])

    def test_select_top_candidates_limits_to_three_by_score(self):
        candidates = [
            {"aweme_id": "a", "priority_score": 1},
            {"aweme_id": "b", "priority_score": 5},
            {"aweme_id": "c", "priority_score": 3},
            {"aweme_id": "d", "priority_score": 2},
        ]
        selected = select_top_candidates(candidates, limit=3)
        self.assertEqual([c["aweme_id"] for c in selected], ["b", "c", "d"])
        self.assertTrue(all(c["candidate_status"] == BATCH_SELECTED_STATUS for c in selected))

    def test_archive_non_top_candidates_marks_only_non_selected_and_keeps_scores(self):
        candidates = [
            {"aweme_id": "a", "priority_score": 10, "caption": "top"},
            {"aweme_id": "b", "priority_score": 8, "caption": "top2"},
            {"aweme_id": "c", "priority_score": 7, "caption": "top3"},
            {"aweme_id": "d", "priority_score": 1, "caption": "archive"},
        ]
        archived = archive_non_top_candidates(candidates, selected_aweme_ids={"a", "b", "c"}, max_archive=1000)
        self.assertEqual([c["aweme_id"] for c in archived], ["d"])
        self.assertEqual(archived[0]["priority_score"], 1)
        self.assertEqual(archived[0]["archive_reason"], "not_top_3")

    def test_parse_keywords_strips_blanks_and_keeps_order(self):
        self.assertEqual(parse_keywords("美女, 甜妹,,国风"), ["美女", "甜妹", "国风"])

    def test_build_search_plan_offsets_each_keyword(self):
        plan = build_search_plan(["美女", "甜妹"], pages=2, count=10)
        self.assertEqual(plan, [
            {"keyword": "美女", "offset": 0, "count": 10},
            {"keyword": "美女", "offset": 10, "count": 10},
            {"keyword": "甜妹", "offset": 0, "count": 10},
            {"keyword": "甜妹", "offset": 10, "count": 10},
        ])

    def test_select_batch_rows_keeps_only_batch_selected_ordered_by_score(self):
        rows = [
            {"aweme_id": "a", "candidate_status": "archived", "priority_score": 100},
            {"aweme_id": "b", "candidate_status": "batch_selected", "priority_score": 5},
            {"aweme_id": "c", "candidate_status": "batch_selected", "priority_score": 9},
        ]
        self.assertEqual([r["aweme_id"] for r in select_batch_rows(rows)], ["c", "b"])

    def test_build_screening_template_has_required_ai_beauty_fields(self):
        template = build_screening_template("123", "analysis/douyin_ai_beauty/123/contact_sheet.jpg")
        self.assertEqual(template["decision"], "review")
        self.assertEqual(template["contact_sheet_path"], "analysis/douyin_ai_beauty/123/contact_sheet.jpg")
        self.assertIn("recommended_tags", template)
        self.assertLessEqual(len(template["recommended_tags"]), 5)

    def test_summarize_video_status_detects_public_processed_ai_beauty(self):
        item = {
            "id": "abc",
            "snippet": {"channelTitle": "AI Beauty", "channelId": "UCEPE24TT9ZpGpVs0vv3i7mw", "title": "T", "description": ""},
            "status": {"privacyStatus": "public", "uploadStatus": "processed"},
            "processingDetails": {"processingStatus": "succeeded"},
            "contentDetails": {"duration": "PT8S"},
        }
        summary = summarize_video_status(item)
        self.assertTrue(summary["ok"])
        self.assertEqual(summary["privacy_status"], "public")
        self.assertEqual(summary["processing_status"], "succeeded")

    def test_summarize_video_status_delayed_requires_succeeded_and_max_five_tags(self):
        item = {
            "id": "abc",
            "snippet": {"channelTitle": "AI Beauty", "channelId": "UCEPE24TT9ZpGpVs0vv3i7mw", "title": "T", "description": "", "tags": ["1", "2", "3", "4", "5", "6"]},
            "status": {"privacyStatus": "public", "uploadStatus": "processed"},
            "processingDetails": {"processingStatus": "processing"},
            "contentDetails": {"duration": "PT8S", "regionRestriction": {"blocked": ["US"]}},
        }
        summary = summarize_video_status(item, delayed=True)
        self.assertFalse(summary["ok"])
        self.assertIn("processing_not_succeeded", summary["problems"])
        self.assertIn("too_many_tags", summary["problems"])
        self.assertIn("region_restriction", summary["problems"])

    def test_should_cleanup_after_decision_for_non_upload_terminal_states(self):
        self.assertTrue(should_cleanup_after_decision("skipped"))
        self.assertTrue(should_cleanup_after_decision("review"))
        self.assertTrue(should_cleanup_after_decision("failed"))
        self.assertFalse(should_cleanup_after_decision("approved"))

    def test_screened_out_status_is_not_active_for_future_reranking(self):
        self.assertEqual(SCREENED_OUT_STATUS, "screened_out")
        self.assertNotIn(SCREENED_OUT_STATUS, ACTIVE_STATUSES)
        self.assertIn(ARCHIVED_STATUS, ACTIVE_STATUSES)
        self.assertIn(NEW_STATUS, ACTIVE_STATUSES)
        self.assertTrue(is_active_status(NEW_STATUS))
        self.assertFalse(is_active_status(SCREENED_OUT_STATUS))
        self.assertTrue(is_terminal_status(SCREENED_OUT_STATUS))
        self.assertTrue(is_terminal_status(UPLOADED_STATUS))
        self.assertIn(BATCH_SELECTED_STATUS, PROCESSABLE_STATUSES)
        self.assertIn(FAILED_STATUS, PROCESSABLE_STATUSES)
        self.assertIn(ARCHIVE_PRUNED_STATUS, TERMINAL_STATUSES)

    def test_state_machine_allows_known_transitions_and_rejects_reactivation(self):
        self.assertTrue(assert_transition_allowed(NEW_STATUS, BATCH_SELECTED_STATUS))
        self.assertTrue(assert_transition_allowed(BATCH_SELECTED_STATUS, SCREENED_OUT_STATUS))
        self.assertTrue(assert_transition_allowed(BATCH_SELECTED_STATUS, UPLOADED_STATUS))
        with self.assertRaises(ValueError):
            assert_transition_allowed(SCREENED_OUT_STATUS, ARCHIVED_STATUS)

    def test_candidate_status_constraint_sql_uses_state_statuses(self):
        sql = build_candidate_status_constraint_sql()
        self.assertIn("ai_beauty_candidates_status_check", sql)
        for status in [NEW_STATUS, ARCHIVED_STATUS, BATCH_SELECTED_STATUS, SCREENED_OUT_STATUS, UPLOADED_STATUS, ARCHIVE_PRUNED_STATUS, FAILED_STATUS]:
            self.assertIn(status, sql)

    def test_invalid_statuses_detects_rows_outside_state_module(self):
        rows = [("archived", 2), ("bad_status", 1), (SCREENED_OUT_STATUS, 3)]
        self.assertEqual(invalid_statuses(rows), {"bad_status": 1})

    def test_build_run_summary_counts_steps_and_blockers(self):
        summary = build_run_summary([
            {"step": "search", "found": 10},
            {"step": "screen", "aweme_id": "a", "decision": "review"},
            {"step": "upload", "aweme_id": "b", "youtube_video_id": "vid"},
            {"step": "blocker", "reason": "quota"},
        ])
        self.assertEqual(summary["step_count"], 4)
        self.assertEqual(summary["uploads"], 1)
        self.assertEqual(summary["screened"], 1)
        self.assertEqual(summary["blockers"], ["quota"])

    def test_run_log_repository_builds_insert_and_finish_payloads(self):
        class FakeResult:
            def fetchone(self):
                return [99]
        class FakeConn:
            def __init__(self):
                self.calls = []
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def execute(self, query, params=None):
                self.calls.append((str(query), params))
                return FakeResult()
            def commit(self):
                pass
        fake = FakeConn()
        repo = RunLogRepository(connect_fn=lambda: fake)
        run_id = repo.start_run("run-1", job_type="unit-test")
        repo.finish_run("run-1", status="ok", summary={"steps": []}, candidates_found=1, candidates_screened=2, videos_uploaded=3, videos_skipped=4)
        self.assertEqual(run_id, 99)
        self.assertIn("INSERT INTO beauty.ai_beauty_run_logs", fake.calls[0][0])
        self.assertIn("UPDATE beauty.ai_beauty_run_logs", fake.calls[1][0])
        self.assertEqual(fake.calls[1][1]["videos_uploaded"], 3)

    def test_validate_channel_identity_accepts_expected_channel(self):
        channel = {"id": "UCEPE24TT9ZpGpVs0vv3i7mw", "title": "AI Beauty", "customUrl": "@ai-beauty-1"}
        result = validate_channel_identity(channel, expect_title="AI Beauty", expect_handle="@ai-beauty-1", expect_channel_id="UCEPE24TT9ZpGpVs0vv3i7mw")
        self.assertTrue(result["ok"])
        self.assertEqual(result["problems"], [])

    def test_validate_channel_identity_rejects_wrong_handle(self):
        channel = {"id": "wrong", "title": "Other", "customUrl": "@other"}
        result = validate_channel_identity(channel, expect_title="AI Beauty", expect_handle="@ai-beauty-1", expect_channel_id="UCEPE24TT9ZpGpVs0vv3i7mw")
        self.assertFalse(result["ok"])
        self.assertGreaterEqual(len(result["problems"]), 1)

    def test_operator_should_continue_until_target_or_blocker(self):
        self.assertTrue(operator_should_continue(uploads_this_run=0, target_uploads=3, hard_blocker=None, active_candidates_available=True))
        self.assertFalse(operator_should_continue(uploads_this_run=3, target_uploads=3, hard_blocker=None, active_candidates_available=True))
        self.assertFalse(operator_should_continue(uploads_this_run=1, target_uploads=3, hard_blocker="quota", active_candidates_available=True))
        self.assertFalse(operator_should_continue(uploads_this_run=1, target_uploads=3, hard_blocker=None, active_candidates_available=False))
        self.assertFalse(operator_should_continue(uploads_this_run=0, target_uploads=3, hard_blocker=None, active_candidates_available=True, iteration=10, max_iterations=10))

    def test_summarize_operator_iteration_counts_uploaded_and_screened_out(self):
        summary = summarize_operator_iteration([
            {"status": "uploaded", "aweme_id": "a"},
            {"status": "screened_not_uploaded", "candidate_status": SCREENED_OUT_STATUS, "aweme_id": "b"},
            {"status": "download_failed", "aweme_id": "c"},
            {"status": "needs_screening", "aweme_id": "d"},
        ])
        self.assertEqual(summary["uploaded"], 1)
        self.assertEqual(summary["screened_out"], 1)
        self.assertEqual(summary["hard_blockers"], ["download_failed:c", "vision_required:d"])

    def test_normalize_duplicate_text_removes_noise_and_case(self):
        self.assertEqual(normalize_duplicate_text("AI Beauty! #Portrait ✨"), "ai beauty portrait")

    def test_assess_text_duplicate_risk_marks_exact_title_high(self):
        risk = assess_text_duplicate_risk(
            {"caption": "Sunlit Outdoor AI Beauty Portrait", "author_name": "a"},
            [{"title": "Sunlit Outdoor AI Beauty Portrait", "tags": ["AI Beauty"]}],
        )
        self.assertEqual(risk["risk"], "high")
        self.assertEqual(risk["signals"][0]["type"], "title_caption_similarity")

    def test_assess_text_duplicate_risk_low_for_unrelated_text(self):
        risk = assess_text_duplicate_risk(
            {"caption": "Completely different black tie dance", "author_name": "a"},
            [{"title": "Soft Mint AI Beauty Portrait", "tags": ["Korean Style"]}],
        )
        self.assertEqual(risk["risk"], "low")

    def test_hamming_distance_counts_bit_differences(self):
        self.assertEqual(hamming_distance(0b1010, 0b0011), 2)

    def test_bilibili_coin_zero_beauty_candidate_is_removed_not_uploaded(self):
        action = decide_bilibili_candidate_action({"is_beauty": True, "coin": 0})
        self.assertEqual(action["action"], "remove_default_favorite")
        self.assertFalse(action["upload"])

    def test_bilibili_non_beauty_stops_before_coin_cleanup(self):
        action = decide_bilibili_candidate_action({"is_beauty": False, "coin": 0})
        self.assertEqual(action["action"], "stop_non_beauty")
        self.assertFalse(action["remove_favorite"])

    def test_bilibili_routing_uses_dance_only_for_clear_dance(self):
        self.assertEqual(route_bilibili_upload({"orientation": "vertical", "clear_dance": True})["profile"], "channelDance")
        routed = route_bilibili_upload({"orientation": "horizontal", "clear_dance": False, "light_movement": True})
        self.assertEqual(routed["profile"], "channelCos")
        self.assertEqual(routed["target_folder"], "美女-横屏")

    def test_build_bilibili_pipeline_plan_includes_guard_and_best_quality_download(self):
        plan = build_bilibili_pipeline_plan(max_items=2, dry_run=True)
        commands = "\n".join(step.get("command", "") for step in plan["steps"])
        self.assertIn("scripts/youtube_profile_guard.py", commands)
        self.assertIn("scripts/bilibili_download_best.py", commands)
        self.assertTrue(plan["dry_run"])

    def test_parse_video_metric_item_extracts_core_public_stats(self):
        item = {
            "id": "vid1",
            "statistics": {"viewCount": "123", "likeCount": "7", "commentCount": "2"},
            "contentDetails": {"duration": "PT10S"},
        }
        parsed = parse_video_metric_item(item)
        self.assertEqual(parsed["youtube_video_id"], "vid1")
        self.assertEqual(parsed["views"], 123)
        self.assertEqual(parsed["likes"], 7)
        self.assertEqual(parsed["comments"], 2)

    def test_build_metric_upsert_params_keeps_raw_metrics_json(self):
        params = build_metric_upsert_params({"youtube_video_id": "vid1", "views": 10, "raw_metrics_json": {"x": 1}}, metric_date="2026-06-29")
        self.assertEqual(params["youtube_video_id"], "vid1")
        self.assertEqual(params["metric_date"], "2026-06-29")
        self.assertIn("raw_metrics_json", params)

    def test_build_strategy_recommendations_uses_evidence_not_anecdote(self):
        uploads = [
            {"youtube_video_id": "a", "tags": ["Portrait", "Outdoor"], "views": 1000, "likes": 50},
            {"youtube_video_id": "b", "tags": ["Dance"], "views": 100, "likes": 2},
        ]
        rec = build_strategy_recommendations(uploads, min_samples=2)
        self.assertEqual(rec["sample_size"], 2)
        self.assertEqual(rec["top_tags"][0]["tag"], "Portrait")
        self.assertIn("evidence", rec)
    def test_summarize_video_status_reports_historical_deleted_local_path(self):
        summary = summarize_local_artifact_state(
            local_video_path="downloads/douyin_ai_beauty/does-not-exist.mp4",
            local_file_deleted=True,
        )
        self.assertEqual(summary["local_video_path_role"], "historical_deleted")
        self.assertFalse(summary["local_path_exists"])
        self.assertTrue(summary["local_file_deleted"])


if __name__ == "__main__":
    unittest.main()
