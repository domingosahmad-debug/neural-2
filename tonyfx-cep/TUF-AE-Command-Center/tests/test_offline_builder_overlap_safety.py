from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "jsx" / "host.jsx"


class OfflineBuilderOverlapSafetyTests(unittest.TestCase):
    def test_original_scenes_are_never_extended_for_transitions(self):
        source = HOST.read_text(encoding="utf-8")
        self.assertNotIn("function offlineExtendScene", source)
        self.assertNotIn("offlineExtendScene(pair.outgoing", source)
        self.assertIn("function offlineTransitionClone", source)
        self.assertIn("[TONYFX_TRANSITION_DUPLICATE]", source)

    def test_transition_ranges_are_capped_to_neighboring_shots(self):
        source = HOST.read_text(encoding="utf-8")
        self.assertIn("function offlineTransitionRange", source)
        self.assertIn("boundary-pair.outgoing.inPoint", source)
        self.assertIn("pair.incoming.outPoint-boundary", source)
        self.assertIn("12*frame", source)

    def test_transition_effects_target_disposable_clones(self):
        source = HOST.read_text(encoding="utf-8")
        self.assertIn("transitionPair.outgoing.property", source)
        self.assertIn("transitionPair.incoming.property", source)
        self.assertNotIn('addTransformEffect(pair.outgoing.property', source)
        self.assertNotIn('addTransformEffect(pair.incoming.property', source)

    def test_exact_builder_uses_the_matched_source_moment(self):
        source = HOST.read_text(encoding="utf-8")
        self.assertIn("function offlineMatchedSourceWindow", source)
        self.assertIn("center-Math.max(0,need)/2", source)
        self.assertIn("sourceLocalIn=Math.max(0,Number(matchWindow.sourceIn)", source)
        self.assertIn("scene.startTime=start-sourceLocalIn", source)
        self.assertIn("[TONYFX_MATCHED_SOURCE]", source)

    def test_music_peak_slots_refuse_calm_candidate_matches(self):
        source = HOST.read_text(encoding="utf-8")
        self.assertIn("requirements.minimumMotionScore", source)
        self.assertIn("is a music-peak slot but its matched footage is too calm", source)
        self.assertIn("TONYFX FIRST HIGHLIGHT", source)
        self.assertIn("TONYFX CLIMAX", source)


if __name__ == "__main__":
    unittest.main()
