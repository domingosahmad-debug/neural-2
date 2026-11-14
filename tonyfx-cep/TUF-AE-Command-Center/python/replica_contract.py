#!/usr/bin/env python3
"""Compile TonyFX analysis into a deterministic, refusal-capable build contract."""

from __future__ import annotations

import hashlib
import json
import math
from fractions import Fraction
from typing import Any


SCHEMA = "tonyfx.replica-builder-contract.v1"
SUPPORTED_FAMILIES = {
    "hard_cut", "cut", "crossfade", "black_dip", "white_flash", "rgb_split",
    "directional_smear", "zoom", "zoom_blur", "impact_shake", "spin_zoom",
    "perspective_push", "mask_wipe", "whip_left", "whip_right", "whip_up",
    "whip_down", "slide_left", "slide_right", "slide_up", "slide_down",
}


def _fraction_text(value: Any) -> str:
    if isinstance(value, str) and "/" in value:
        return str(Fraction(value))
    return str(Fraction(str(float(value or 30))).limit_denominator(100_000))


def _curve_controls(event: dict[str, Any]) -> list[float] | None:
    candidates = [
        ((event.get("advancedCurve") or {}).get("controls")),
        ((event.get("strictRecipe") or {}).get("controls")),
        ((event.get("strictRecipe") or {}).get("curve")),
        event.get("curve"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str):
            candidate = candidate.split(",")
        if isinstance(candidate, (list, tuple)) and len(candidate) == 4:
            try:
                values = [float(item) for item in candidate]
            except (TypeError, ValueError):
                continue
            if all(math.isfinite(item) for item in values) and 0 <= values[0] <= 1 and 0 <= values[2] <= 1 and -2 <= values[1] <= 3 and -2 <= values[3] <= 3:
                return [round(item, 6) for item in values]
    return None


def _direction(family: str, event: dict[str, Any]) -> str:
    explicit = str(event.get("direction") or "").lower()
    if explicit in {"in", "out", "in_out", "left", "right", "up", "down", "none", "custom"}:
        return explicit
    for value in ("left", "right", "up", "down"):
        if value in family:
            return value
    ratio = float(event.get("zoomRatio") or 1)
    if "zoom" in family:
        return "in" if ratio >= 1 else "out"
    return "none"


def _family_list(event: dict[str, Any]) -> list[str]:
    forensic = event.get("forensics") or {}
    values = forensic.get("measuredFamilies") or event.get("componentFamilies") or [event.get("family") or "hard_cut"]
    result: list[str] = []
    for item in values:
        value = str(item.get("family") if isinstance(item, dict) else item).lower()
        if value and value not in result:
            result.append(value)
    return result or ["hard_cut"]


def _provider_ambiguities(report: dict[str, Any]) -> list[dict[str, Any]]:
    replica = report.get("replicaLab") or {}
    if not replica.get("available"):
        return [{
            "code": "provider.replica_lab_unavailable",
            "blocking": True,
            "status": "open",
            "message": str(replica.get("reason") or "Deep Replica Lab evidence was not produced."),
        }]
    bundle = replica.get("bundle") or {}
    result: list[dict[str, Any]] = []
    measured_events = report.get("events") or []
    for item in bundle.get("ambiguities") or []:
        frame = int(item.get("frame") or 0)
        corroborating = [event for event in measured_events if event.get("kind") == "cut_transition" and abs(int(event.get("frame") or 0) - frame) <= 2]
        resolved = any(
            float(event.get("confidence") or 0) >= 0.76
            and float((event.get("forensics") or {}).get("confidence") or event.get("confidence") or 0) >= 0.58
            for event in corroborating
        )
        result.append({
            "code": "detector." + str(item.get("kind") or "disagreement"),
            "frame": frame,
            "blocking": item.get("blocking") is True,
            "status": "resolved" if resolved else str(item.get("status") or "open"),
            "message": "OpenCV and TransNetV2 did not agree; TonyFX transition forensics independently corroborated this boundary." if resolved else "OpenCV and TransNetV2 did not agree at this reference frame.",
        })
    return result


def _repeat_groups(repeats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for index, item in enumerate(repeats):
        shot = int(item.get("shot") or 0)
        match = int(item.get("matchesShot") or 0)
        if shot <= 0 or match <= 0 or match >= shot:
            continue
        current_direction = "reverse" if str(item.get("kind") or "").lower() == "reverse" else "forward"
        groups.append({
            "id": f"repeat_{index + 1:03d}",
            "shots": [match, shot],
            "directions": ["forward", current_direction],
            "expectedDirections": ["forward", current_direction],
            "confidence": round(float(item.get("confidence") or 0), 4),
            "sourceRangeMustMatch": True,
        })
    return groups


def compile_builder_contract(report: dict[str, Any]) -> dict[str, Any]:
    media = report.get("media") or {}
    fps = float(media.get("fps") or 30)
    total_frames = int((report.get("summary") or {}).get("decodedFrameCount") or media.get("frames") or 0)
    shots = report.get("shots") or []
    events = report.get("events") or []
    ambiguities = _provider_ambiguities(report)
    transitions: list[dict[str, Any]] = []
    zoom_windows: list[tuple[int, int]] = []
    narrative = report.get("narrativeMap") or (report.get("editBlueprint") or {}).get("narrativeMap") or {}

    for index, event in enumerate(events):
        families = _family_list(event)
        primary = str(event.get("family") or families[0]).lower()
        controls = _curve_controls(event)
        start = max(0, int(event.get("startFrame", event.get("frame", 0))))
        end_exclusive = min(total_frames, max(start + 1, int(event.get("endFrame", start)) + 1))
        cut = int(event.get("frame") or start)
        kind = str(event.get("kind") or "cut_transition")
        confidence = max(float(event.get("confidence") or 0), float((event.get("forensics") or {}).get("confidence") or 0))
        unsupported = [family for family in families if family not in SUPPORTED_FAMILIES]
        needs_curve = any(family not in {"hard_cut", "cut"} for family in families)
        if unsupported:
            ambiguities.append({"code": "transition.unsupported_family", "frame": cut, "blocking": True, "status": "open", "message": ", ".join(unsupported)})
        if needs_curve and controls is None:
            ambiguities.append({"code": "transition.curve_missing", "frame": cut, "blocking": True, "status": "open", "message": "No measured four-control curve exists for this visible transition."})
        if confidence < 0.58 and any(family not in {"hard_cut", "cut"} for family in families):
            ambiguities.append({"code": "transition.low_confidence", "frame": cut, "blocking": True, "status": "open", "message": f"Transition confidence is {confidence:.3f}."})
        zoom_owner = "transition" if any("zoom" in family for family in families) else "none"
        if zoom_owner == "transition":
            zoom_windows.append((start, end_exclusive))
        transitions.append({
            "id": f"transition_{index + 1:03d}",
            "kind": kind,
            "cutFrame": cut,
            "frames": [start, end_exclusive],
            "time": round(cut / fps, 9),
            "families": families,
            "primary": primary,
            "direction": _direction(primary, event),
            "durationFrames": end_exclusive - start,
            "curve": {"kind": "cubic_bezier", "controls": controls, "source": str(event.get("curveSource") or "measured transition evidence")} if controls else None,
            "zoomOwner": zoom_owner,
            "confidence": round(confidence, 4),
            "aeRecipe": (event.get("strictRecipe") or {}).get("aeRecipe") or event.get("aeRecipe") or [],
            "supported": not unsupported,
            "evidence": {
                "stableContentChange": event.get("stableContentChange"),
                "candidateAgreement": event.get("renderedCandidateAgreement"),
                "forensicsAvailable": bool((event.get("forensics") or {}).get("available")),
            },
        })

    contract_shots: list[dict[str, Any]] = []
    for index, shot in enumerate(shots):
        start = int(shot.get("startFrame") or 0)
        duration = int(shot.get("durationFrames") or 0)
        end_exclusive = start + max(1, duration)
        direction = str(shot.get("zoomDirection") or "none").lower()
        ratio = float(shot.get("zoomRatio") or 1)
        zoom_enabled = direction in {"in", "out"} and abs(math.log(max(ratio, 1e-9))) >= 0.032
        zoom_start, zoom_end = start, end_exclusive
        for window_start, window_end in zoom_windows:
            if zoom_start < window_end and zoom_end > window_start:
                if window_start <= zoom_start:
                    zoom_start = max(zoom_start, window_end)
                else:
                    zoom_end = min(zoom_end, window_start)
        if zoom_end - zoom_start < 3:
            zoom_enabled = False
        controls = _curve_controls(shot)
        if zoom_enabled and controls is None:
            ambiguities.append({"code": "scene.zoom_curve_missing", "shot": index + 1, "blocking": True, "status": "open", "message": "Measured scene zoom has no executable curve."})
        reference_motion = shot.get("translationPx") or {}
        semantic = shot.get("semantic") or {}
        best_matches = shot.get("footageMatches") or semantic.get("rankedProjectMatches") or []
        minimum_motion = float(semantic.get("minimumCandidateMotion") or 0.0)
        flashy_required = bool(semantic.get("flashyRequired"))
        if flashy_required and best_matches and max(float(item.get("motionScore") or 0.0) for item in best_matches) + 1e-6 < minimum_motion:
            ambiguities.append({
                "code": "shot.peak_energy_candidate_missing", "shot": index + 1, "blocking": True, "status": "open",
                "message": f"Peak slot requires candidate motion >= {minimum_motion:.3f}, but the indexed matches are calmer.",
            })
        contract_shots.append({
            "id": f"shot_{index + 1:03d}",
            "index": index + 1,
            "compFrames": [start, end_exclusive],
            "startTime": round(start / fps, 9),
            "endTime": round(end_exclusive / fps, 9),
            "durationFrames": end_exclusive - start,
            "duration": round((end_exclusive - start) / fps, 9),
            "zoomDirection": direction,
            "zoomRatio": round(ratio, 6),
            "motionPlan": {
                "zoom": {
                    "enabled": zoom_enabled,
                    "owner": "scene" if zoom_enabled else "none",
                    "frames": [zoom_start, zoom_end],
                    "direction": direction,
                    "ratio": round(ratio, 6),
                    "curve": {"kind": "cubic_bezier", "controls": controls} if controls else None,
                },
                "referenceTranslationPx": {"x": float(reference_motion.get("x") or 0), "y": float(reference_motion.get("y") or 0)},
            },
            "sourceRequirements": {
                "minimumFrames": end_exclusive - start,
                "continuousShotRequired": True,
                "nativeSpeedRequired": True,
                "wideRequired": direction in {"in", "out"} and abs(math.log(max(ratio, 1e-9))) >= 0.065,
                "minimumMatchConfidence": 0.42 if best_matches else 0,
                "matchedSourceWindowRequired": bool(best_matches),
                "minimumMotionScore": round(minimum_motion, 4),
                "flashyActionRequired": flashy_required,
                "mouthMotionPolicy": str(semantic.get("mouthMotionPolicy") or "avoid_visible_speech_without_aligned_dialogue"),
            },
            "footageMatches": best_matches[:8],
            "semantic": semantic,
            "narrativePhase": str(semantic.get("phase") or ""),
            "editorialFunction": str(semantic.get("editorialFunction") or semantic.get("role") or ""),
            "peakPriority": int(semantic.get("peakPriority") or 0),
            "energy": {
                "visual": float(semantic.get("visualEnergyScore") or 0),
                "audio": float(semantic.get("audioEnergyScore") or 0),
                "combined": float(semantic.get("energyScore") or 0),
            },
            "framing": shot.get("visionSubject") or shot.get("framing") or {},
        })

    cut_frames = [int(item["cutFrame"]) for item in transitions if item["kind"] == "cut_transition"]
    expected = [item["compFrames"][1] for item in contract_shots[:-1]]
    if cut_frames != expected:
        ambiguities.append({
            "code": "timeline.cut_scene_mismatch",
            "blocking": True,
            "status": "open",
            "message": f"Cut frames {cut_frames} do not exactly equal shot boundaries {expected}.",
        })
    for left, right in zip(contract_shots, contract_shots[1:]):
        if left["compFrames"][1] != right["compFrames"][0]:
            ambiguities.append({"code": "timeline.coverage", "blocking": True, "status": "open", "message": "Reference shot ranges contain a gap or overlap."})
            break

    audio = report.get("audio") or {}
    audio_events: list[dict[str, Any]] = []
    for kind in ("beats", "onsets", "downbeats", "drops"):
        for value in audio.get(kind) or []:
            frame = int(round(float(value) * fps))
            if 0 <= frame < total_frames:
                audio_events.append({"frame": frame, "kind": kind[:-1] if kind.endswith("s") else kind})
    audio_events.sort(key=lambda item: (item["frame"], item["kind"]))
    blockers = [item for item in ambiguities if item.get("blocking") is True and item.get("status") != "resolved"]
    contract: dict[str, Any] = {
        "schema": SCHEMA,
        "version": 1,
        "reference": {
            "path": media.get("path"), "width": int(media.get("width") or 0), "height": int(media.get("height") or 0),
            "fps": _fraction_text(media.get("fpsRational") or media.get("fps") or 30), "totalFrames": total_frames,
        },
        "timingUnit": "half_open_reference_frames",
        "shots": contract_shots,
        "transitions": transitions,
        "repeatGroups": _repeat_groups(report.get("repeats") or []),
        "audio": {"alignmentFrame": 0, "events": audio_events},
        "narrative": narrative,
        "ambiguities": ambiguities,
        "buildGate": {
            "exactReady": len(blockers) == 0 and bool(contract_shots),
            "blockingCount": len(blockers),
            "blockingCodes": [str(item.get("code")) for item in blockers],
            "creativeDecisionsAllowedInAE": False,
            "genericCurveFallbackAllowed": False,
            "genericEffectFallbackAllowed": False,
            "nativeDialogueSpeedRequired": True,
            "singleZoomOwnerRequired": True,
            "visionMatchedSourceMomentRequired": True,
            "peakEnergyMappingRequired": bool(narrative.get("available")),
            "dialogueVisualCoherenceRequired": True,
        },
    }
    digest_source = json.dumps(contract, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    contract["certificate"] = {"schema": "tonyfx.replica-contract-certificate.v1", "sha256": hashlib.sha256(digest_source).hexdigest()}
    return contract


def validate_builder_contract(contract: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if contract.get("schema") != SCHEMA:
        issues.append("schema.invalid")
    shots = contract.get("shots") or []
    if not shots:
        issues.append("shots.missing")
    for index, shot in enumerate(shots):
        frames = shot.get("compFrames") or []
        if len(frames) != 2 or not all(isinstance(value, int) for value in frames) or frames[0] >= frames[1]:
            issues.append(f"shots[{index}].frames.invalid")
        zoom = (shot.get("motionPlan") or {}).get("zoom") or {}
        if zoom.get("enabled") and zoom.get("owner") != "scene":
            issues.append(f"shots[{index}].zoom.owner")
        if zoom.get("enabled") and not ((zoom.get("curve") or {}).get("controls")):
            issues.append(f"shots[{index}].zoom.curve")
    for index, transition in enumerate(contract.get("transitions") or []):
        if not transition.get("supported"):
            issues.append(f"transitions[{index}].unsupported")
        if any(family not in {"hard_cut", "cut"} for family in transition.get("families") or []) and not ((transition.get("curve") or {}).get("controls")):
            issues.append(f"transitions[{index}].curve")
    if (contract.get("buildGate") or {}).get("blockingCount") != len([item for item in contract.get("ambiguities") or [] if item.get("blocking") and item.get("status") != "resolved"]):
        issues.append("buildGate.blockingCount")
    return issues
