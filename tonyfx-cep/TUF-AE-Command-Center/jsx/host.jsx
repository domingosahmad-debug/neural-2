var TUF = TUF || {};

(function (api) {
    function quoteString(value) {
        return '"' + String(value)
            .replace(/\\/g, "\\\\")
            .replace(/"/g, '\\"')
            .replace(/\r/g, "\\r")
            .replace(/\n/g, "\\n")
            .replace(/\t/g, "\\t") + '"';
    }

    function safeStringify(value) {
        if (value === null) { return "null"; }
        var type = typeof value;
        if (type === "string") { return quoteString(value); }
        if (type === "number") { return isFinite(value) ? String(value) : "null"; }
        if (type === "boolean") { return value ? "true" : "false"; }
        if (value instanceof Array) {
            var items = [];
            for (var i = 0; i < value.length; i++) { items.push(safeStringify(value[i])); }
            return "[" + items.join(",") + "]";
        }
        if (type === "object") {
            var pairs = [];
            for (var key in value) {
                if (value.hasOwnProperty(key) && typeof value[key] !== "undefined" && typeof value[key] !== "function") {
                    pairs.push(quoteString(key) + ":" + safeStringify(value[key]));
                }
            }
            return "{" + pairs.join(",") + "}";
        }
        return "null";
    }

    function parseJSON(value) {
        if (typeof JSON !== "undefined" && JSON.parse) {
            try { return JSON.parse(value); } catch (ignoreNativeJSON) {}
        }
        return eval("(" + value + ")");
    }

    function response(data) {
        try {
            var result = JSON.stringify(data);
            if (result && typeof result === "string") { return result; }
        } catch (ignoreNativeJSON) {}
        try { return safeStringify(data); }
        catch (error) { return '{"ok":false,"error":"Could not serialize the AE result."}'; }
    }

    function activeComp() {
        var comp = app.project ? app.project.activeItem : null;
        if (!(comp instanceof CompItem)) { throw new Error("Open the intended composition first."); }
        return comp;
    }

    function selectedLayers(comp) {
        return comp.selectedLayers || [];
    }

    function isProtected(layer) {
        return /\[TUF_PROTECTED\]/i.test(layer.comment || "") || /(intro|user area|do not edit|protected)/i.test(layer.name) || layer.locked;
    }

    function effectByMatchOrName(effects, matchName, namePattern) {
        if (!effects) { return null; }
        for (var i = 1; i <= effects.numProperties; i++) {
            var effect = effects.property(i);
            if (effect.matchName === matchName || namePattern.test(effect.name)) { return effect; }
        }
        return null;
    }

    function propertyByNames(group, names) {
        for (var i = 0; i < names.length; i++) {
            var property = group.property(names[i]);
            if (property) { return property; }
        }
        return null;
    }

    function propertyByNamesOrIndex(group, names, fallbackIndex) {
        var property = propertyByNames(group, names);
        if (!property && fallbackIndex && group && group.numProperties >= fallbackIndex) {
            try { property = group.property(fallbackIndex); } catch (ignore) {}
        }
        return property;
    }

    function setProperty(group, names, value) {
        var property = propertyByNames(group, names);
        if (property) { property.setValue(value); return true; }
        return false;
    }

    function groupByPattern(root, pattern) {
        if (!root || !root.numProperties) { return null; }
        for (var i = 1; i <= root.numProperties; i++) {
            var child = root.property(i);
            if (pattern.test(child.name || "")) { return child; }
        }
        for (var j = 1; j <= root.numProperties; j++) {
            var nested = root.property(j);
            if (nested && nested.numProperties) {
                var found = groupByPattern(nested, pattern);
                if (found) { return found; }
            }
        }
        return null;
    }

    function leafByPattern(root, pattern, valueType) {
        if (!root || !root.numProperties) { return null; }
        for (var i = 1; i <= root.numProperties; i++) {
            var child = root.property(i);
            if (child && child.propertyType === PropertyType.PROPERTY && pattern.test(child.name || "")) {
                if (!valueType || child.propertyValueType === valueType) { return child; }
            }
        }
        for (var j = 1; j <= root.numProperties; j++) {
            var nested = root.property(j);
            if (nested && nested.numProperties) {
                var found = leafByPattern(nested, pattern, valueType);
                if (found) { return found; }
            }
        }
        return null;
    }

    function setSectionValue(effect, sectionPattern, propertyPattern, value) {
        var section = groupByPattern(effect, sectionPattern);
        var property = section ? leafByPattern(section, propertyPattern) : null;
        if (!property) { return false; }
        try { property.setValue(value); return true; } catch (ignore) { return false; }
    }

    function readSectionValue(effect, sectionPattern, propertyPattern) {
        var section = groupByPattern(effect, sectionPattern);
        var property = section ? leafByPattern(section, propertyPattern) : null;
        if (!property) { return null; }
        try { return property.value; } catch (ignore) { return null; }
    }

    function selectedFootageTargets(comp) {
        var selected = selectedLayers(comp), result = [];
        for (var i = 0; i < selected.length; i++) {
            if (isProtected(selected[i])) { continue; }
            var targets = footageTargets(selected[i]);
            for (var j = 0; j < targets.length; j++) { result.push(targets[j]); }
        }
        return result;
    }

    function ensureLumetri(layer) {
        var effects = layer.property("ADBE Effect Parade");
        var lumetri = effectByExactName(effects, "LUMETRI - TONYFX COLOR STUDIO");
        if (!lumetri) { lumetri = effects.addProperty("ADBE Lumetri"); }
        try { lumetri.name = "LUMETRI - TONYFX COLOR STUDIO"; } catch (ignoreName) {}
        try { lumetri.moveTo(1); } catch (ignoreMove) {}
        lumetri = effectByExactName(effects, "LUMETRI - TONYFX COLOR STUDIO");
        moveMotionTileAfterLumetri(effects);
        lumetri = effectByExactName(effects, "LUMETRI - TONYFX COLOR STUDIO");
        return lumetri;
    }

    var COLOR_MATCH_EFFECT_NAME = "LUMETRI - TONYFX COLOR MATCH";

    function effectByExactName(effects, name) {
        if (!effects) { return null; }
        for (var i = 1; i <= effects.numProperties; i++) {
            if (String(effects.property(i).name) === String(name)) { return effects.property(i); }
        }
        return null;
    }

    function moveMotionTileAfterLumetri(effects) {
        var tile = effectByMatchOrName(effects, "ADBE Tile", /motion tile/i);
        if (!tile) { return; }
        var lumetriCount = 0;
        for (var i = 1; i <= effects.numProperties; i++) {
            if (String(effects.property(i).matchName) === "ADBE Lumetri") { lumetriCount++; }
        }
        try { tile.moveTo(Math.min(effects.numProperties, lumetriCount + 1)); } catch (ignoreTileOrder) {}
    }

    function selectedColorTargets(comp) {
        var layers = selectedLayers(comp), result = [];
        for (var i = 0; i < layers.length; i++) {
            var layer = layers[i];
            if (isProtected(layer) || layer.adjustmentLayer || layer.nullLayer || !layer.hasVideo) { continue; }
            result.push(layer);
        }
        return result;
    }

    function ensureColorMatchLumetri(layer) {
        var effects = layer.property("ADBE Effect Parade");
        if (!effects) { throw new Error("The selected layer cannot receive effects."); }
        var lumetri = effectByExactName(effects, COLOR_MATCH_EFFECT_NAME);
        if (!lumetri) {
            lumetri = effects.addProperty("ADBE Lumetri");
            lumetri.name = COLOR_MATCH_EFFECT_NAME;
        }
        try { lumetri.moveTo(1); } catch (ignoreMove) {}
        lumetri = effectByExactName(effects, COLOR_MATCH_EFFECT_NAME);
        moveMotionTileAfterLumetri(effects);
        lumetri = effectByExactName(effects, COLOR_MATCH_EFFECT_NAME);
        return lumetri;
    }

    var LUMETRI_CONTROL_IDS = {
        temperature:15, tint:16, saturation:17,
        exposure:20, contrast:21, highlights:22, shadows:23, whites:24, blacks:25,
        fadedFilm:39, sharpen:40, vibrance:41, creativeSaturation:42,
        vignetteAmount:109, vignetteMidpoint:110, vignetteRoundness:111, vignetteFeather:112
    };

    function lumetriControl(effect, key) {
        if (!effect || !LUMETRI_CONTROL_IDS[key]) { return null; }
        try { return effect.property(LUMETRI_CONTROL_IDS[key]); } catch (ignore) { return null; }
    }

    function setLumetriControl(effect, key, value) {
        var property = lumetriControl(effect, key);
        if (!property) { return false; }
        try { property.setValue(Number(value)); return Math.abs(Number(property.value) - Number(value)) < 0.001; } catch (ignore) { return false; }
    }

    function readLumetriControl(effect, key) {
        var property = lumetriControl(effect, key);
        if (!property) { return null; }
        try { return Number(property.value); } catch (ignore) { return null; }
    }

    function wheelTonePattern(tone) {
        if (tone === "midtones") { return /(midtone|middle)/i; }
        return new RegExp(tone.replace(/s$/, ""), "i");
    }

    function applyWheel(effect, tone, data) {
        var wheels = groupByPattern(effect, /color wheels/i);
        if (!wheels || !data) { return 0; }
        var toneGroup = groupByPattern(wheels, wheelTonePattern(tone));
        if (!toneGroup) { return 0; }
        var changed = 0;
        var color = leafByPattern(toneGroup, /(color|tint|hue)/i, PropertyValueType.COLOR);
        if (color && data.color && data.color.length >= 3) {
            try { color.setValue([data.color[0] / 255, data.color[1] / 255, data.color[2] / 255, 1]); changed++; } catch (ignoreColor) {}
        }
        var luma = leafByPattern(toneGroup, /(luma|level|brightness)/i);
        if (luma) { try { luma.setValue(Number(data.luma) || 0); changed++; } catch (ignoreLuma) {} }
        return changed;
    }

    function footageTargets(layer) {
        var result = [];
        if (layer.source && layer.source instanceof CompItem) {
            for (var i = 1; i <= layer.source.numLayers; i++) {
                var inner = layer.source.layer(i);
                if (inner.source && inner.source instanceof FootageItem && inner.hasVideo) { result.push(inner); }
            }
        } else if (layer.source && layer.source instanceof FootageItem && layer.hasVideo) {
            result.push(layer);
        }
        return result;
    }

    function collectSnapshot(comp) {
        var guards = [];
        var protectedCount = 0;
        var wrongOrder = 0;
        var adjustmentBelow = 0;
        for (var i = 1; i <= comp.numLayers; i++) {
            var layer = comp.layer(i);
            if (isProtected(layer)) { protectedCount++; }
            var effects = layer.property("ADBE Effect Parade");
            var lumetri = effectByMatchOrName(effects, "ADBE Lumetri", /lumetri/i);
            var tile = effectByMatchOrName(effects, "ADBE Tile", /motion tile/i);
            if (lumetri && tile && tile.propertyIndex < lumetri.propertyIndex) { wrongOrder++; }
            if (layer.adjustmentLayer && i > 1) {
                var layerAbove = comp.layer(i - 1);
                if (layerAbove && !layerAbove.adjustmentLayer && layerAbove.inPoint < layer.outPoint && layerAbove.outPoint > layer.inPoint) { adjustmentBelow++; }
            }
        }
        if (comp.width !== 1080 || comp.height !== 1080) { guards.push("Warning: active composition is not 1080x1080."); }
        if (Math.abs(comp.frameRate - 24) > 0.01 && Math.abs(comp.frameRate - 25) > 0.01 && Math.abs(comp.frameRate - 30) > 0.01) { guards.push("Warning: frame rate is outside the approved 24, 25, or 30 fps set."); }
        if (wrongOrder) { guards.push("Warning: " + wrongOrder + " layer(s) have Motion Tile above Lumetri."); }
        if (adjustmentBelow) { guards.push("Warning: " + adjustmentBelow + " adjustment layer(s) may sit below footage."); }
        guards.push(protectedCount + " protected or locked layer(s) detected.");
        return {
            ok: true,
            comp: {
                name: comp.name,
                width: comp.width,
                height: comp.height,
                frameRate: comp.frameRate,
                duration: comp.duration,
                layers: comp.numLayers,
                selected: selectedLayers(comp).length
            },
            guards: guards
        };
    }

    api.applyLumetri = function (json) {
        try {
            var values = parseJSON(json), comp = activeComp(), targets = selectedFootageTargets(comp);
            if (!targets.length) { throw new Error("Select one or more unprotected scene layers first."); }
            var applied = 0, skipped = [];
            app.beginUndoGroup("TonyFX Color Studio");
            for (var t = 0; t < targets.length; t++) {
                var lumetri = ensureLumetri(targets[t]);
                for (var key in LUMETRI_CONTROL_IDS) {
                    if (!LUMETRI_CONTROL_IDS.hasOwnProperty(key) || values[key] === undefined) { continue; }
                    if (setLumetriControl(lumetri, key, values[key])) { applied++; }
                    else if (t === 0) { skipped.push(key); }
                }
                if (values.wheels) {
                    var wheelCount = applyWheel(lumetri, "shadows", values.wheels.shadows) + applyWheel(lumetri, "midtones", values.wheels.midtones) + applyWheel(lumetri, "highlights", values.wheels.highlights);
                    if (!wheelCount && t === 0) { skipped.push("color wheels (use native Advanced controls in this AE build)"); }
                    applied += wheelCount;
                }
            }
            app.endUndoGroup();
            var snapshot = collectSnapshot(comp);
            return response({ok:true,message:"Color Studio applied " + applied + " Lumetri control updates across " + targets.length + " footage layer(s)." + (skipped.length ? " Unavailable: " + skipped.join(", ") + "." : ""),comp:snapshot.comp,guards:snapshot.guards,skipped:skipped});
        } catch (error) { try { app.endUndoGroup(); } catch (ignore) {} return response({ok:false,error:error.toString() + (error.line ? " at line " + error.line : "")}); }
    };

    api.readLumetriSelected = function () {
        try {
            var comp = activeComp(), targets = selectedFootageTargets(comp);
            if (!targets.length) { throw new Error("Select an unprotected scene layer first."); }
            var effects = targets[0].property("ADBE Effect Parade"), lumetri = effectByExactName(effects, "LUMETRI - TONYFX COLOR STUDIO");
            if (!lumetri) { throw new Error("The selected footage has no Lumetri effect yet."); }
            var values = {};
            for (var key in LUMETRI_CONTROL_IDS) {
                if (!LUMETRI_CONTROL_IDS.hasOwnProperty(key)) { continue; }
                var value = readLumetriControl(lumetri, key);
                if (value !== null) { values[key] = value; }
            }
            return response({ok:true,message:"Loaded Lumetri values from " + targets[0].name + ".",values:values});
        } catch (error) { return response({ok:false,error:error.toString()}); }
    };

    api.resetLumetriSelected = function () {
        try {
            var comp = activeComp(), targets = selectedFootageTargets(comp);
            if (!targets.length) { throw new Error("Select one or more unprotected scene layers first."); }
            app.beginUndoGroup("TonyFX Reset Lumetri");
            for (var i = 0; i < targets.length; i++) {
                var effects = targets[i].property("ADBE Effect Parade"), lumetri = effectByExactName(effects, "LUMETRI - TONYFX COLOR STUDIO");
                if (lumetri) { lumetri.remove(); }
                ensureLumetri(targets[i]);
            }
            app.endUndoGroup();
            return response({ok:true,message:"Reset Lumetri to neutral on " + targets.length + " footage layer(s)."});
        } catch (error) { try { app.endUndoGroup(); } catch (ignore) {} return response({ok:false,error:error.toString()}); }
    };

    api.getColorMatchSelection = function () {
        try {
            var comp = activeComp(), layers = selectedLayers(comp);
            if (layers.length !== 1) { throw new Error("Select exactly one target or reference video layer."); }
            var layer = layers[0];
            if (isProtected(layer) || layer.adjustmentLayer || layer.nullLayer || !layer.hasVideo) { throw new Error("Choose one unprotected scene layer with video."); }
            var resolved = resolveLocalMediaRange(layer, layer.inPoint, layer.outPoint, comp.frameDuration, 0);
            var sourceDuration = Math.max(comp.frameDuration, resolved.end - resolved.start);
            return response({ok:true,path:resolved.file.fsName,layerName:layer.name,layerIndex:layer.index,compName:comp.name,compIn:layer.inPoint,compOut:layer.outPoint,compDuration:layer.outPoint-layer.inPoint,sourceStart:resolved.start,sourceDuration:sourceDuration,reverse:resolved.reverse,timeRemapped:resolved.timeRemapped,fromPrecomp:layer.source instanceof CompItem});
        } catch (error) { return response({ok:false,error:error.toString() + (error.line ? " at line " + error.line : "")}); }
    };

    api.applyColorMatch = function (json) {
        var undoOpen = false;
        try {
            var options = parseJSON(json), values = options.values || {}, comp = activeComp(), targets = selectedColorTargets(comp);
            if (!targets.length) { throw new Error("Select one or more unprotected scene layers for Color Match."); }
            app.beginUndoGroup("TonyFX Apply Editable Color Match"); undoOpen = true;
            var applied = 0, skipped = [];
            for (var i = 0; i < targets.length; i++) {
                var effect = ensureColorMatchLumetri(targets[i]);
                for (var key in LUMETRI_CONTROL_IDS) {
                    if (!LUMETRI_CONTROL_IDS.hasOwnProperty(key) || values[key] === undefined) { continue; }
                    if (setLumetriControl(effect, key, values[key])) { applied++; }
                    else if (i === 0) { skipped.push(key); }
                }
                try { targets[i].comment = String(targets[i].comment || "") + "\nTONYFX_COLOR_MATCH:" + String(options.matchId || "local"); } catch (ignoreComment) {}
            }
            app.endUndoGroup(); undoOpen = false;
            return response({ok:true,message:"Applied a dedicated editable Color Match effect to " + targets.length + " layer" + (targets.length === 1 ? "." : "s."),layers:targets.length,controls:applied,skipped:skipped});
        } catch (error) { if (undoOpen) { try { app.endUndoGroup(); } catch (ignoreUndo) {} } return response({ok:false,error:error.toString() + (error.line ? " at line " + error.line : "")}); }
    };

    api.removeColorMatch = function () {
        var undoOpen = false;
        try {
            var comp = activeComp(), targets = selectedColorTargets(comp);
            if (!targets.length) { throw new Error("Select one or more scene layers first."); }
            app.beginUndoGroup("TonyFX Remove Color Match"); undoOpen = true;
            var removed = 0;
            for (var i = 0; i < targets.length; i++) {
                var effects = targets[i].property("ADBE Effect Parade"), effect = effectByExactName(effects, COLOR_MATCH_EFFECT_NAME);
                if (effect) { effect.remove(); removed++; }
            }
            app.endUndoGroup(); undoOpen = false;
            return response({ok:true,message:removed ? "Removed TonyFX Color Match from " + removed + " layer" + (removed === 1 ? "." : "s.") : "No TonyFX Color Match effect was found on the selection.",removed:removed});
        } catch (error) { if (undoOpen) { try { app.endUndoGroup(); } catch (ignoreUndo) {} } return response({ok:false,error:error.toString()}); }
    };

    api.inspectActiveComp = function () {
        try {
            var result = collectSnapshot(activeComp());
            result.message = "Active composition inspected without changes.";
            return response(result);
        } catch (error) { return response({ok: false, error: error.toString()}); }
    };

    api.toggleProtectSelected = function () {
        try {
            var comp = activeComp();
            var layers = selectedLayers(comp);
            if (!layers.length) { throw new Error("Select one or more layers first."); }
            var protectedNow = 0;
            app.beginUndoGroup("TUF Toggle Layer Protection");
            for (var i = 0; i < layers.length; i++) {
                var comment = layers[i].comment || "";
                if (/\[TUF_PROTECTED\]/i.test(comment)) {
                    layers[i].comment = comment.replace(/\s*\[TUF_PROTECTED\]\s*/ig, " ").replace(/^\s+|\s+$/g, "");
                } else {
                    layers[i].comment = (comment ? comment + " " : "") + "[TUF_PROTECTED]";
                    protectedNow++;
                }
            }
            app.endUndoGroup();
            var result = collectSnapshot(comp);
            result.message = "Protection toggled on " + layers.length + " layer(s); " + protectedNow + " are now protected.";
            return response(result);
        } catch (error) { try { app.endUndoGroup(); } catch (ignore) {} return response({ok: false, error: error.toString()}); }
    };

    function uniqueItemName(base) {
        var name = safeLayerName(base), candidate = name, suffix = 2, exists = true;
        while (exists) {
            exists = false;
            for (var i = 1; i <= app.project.numItems; i++) {
                if (app.project.item(i).name === candidate) { exists = true; break; }
            }
            if (exists) { candidate = name + " " + suffix++; }
        }
        return candidate;
    }

    function selectedRange(comp, layers) {
        var start = layers.length ? layers[0].inPoint : 0, end = layers.length ? layers[0].outPoint : comp.duration, top = layers.length ? layers[0] : null;
        for (var i = 1; i < layers.length; i++) {
            start = Math.min(start, layers[i].inPoint); end = Math.max(end, layers[i].outPoint);
            if (layers[i].index < top.index) { top = layers[i]; }
        }
        return {start:Math.max(0,start),end:Math.min(comp.duration,end),top:top};
    }

    function finishTrimmedPrecomp(parentComp, precomp, start, end) {
        var duration = Math.max(parentComp.frameDuration, end - start), outer = null;
        for (var i = 1; i <= precomp.numLayers; i++) { precomp.layer(i).startTime -= start; }
        precomp.duration = duration; precomp.workAreaStart = 0; precomp.workAreaDuration = duration;
        for (var p = 1; p <= parentComp.numLayers; p++) { if (parentComp.layer(p).source === precomp) { outer = parentComp.layer(p); break; } }
        if (!outer) { throw new Error("After Effects did not return the new precomp layer."); }
        outer.startTime = start; outer.inPoint = start; outer.outPoint = end;
        outer.selected = true;
        return outer;
    }

    function selectedLayerDescriptors(layers) {
        var descriptors = [];
        for (var i = 0; i < layers.length; i++) {
            descriptors.push({
                index: layers[i].index,
                name: layers[i].name,
                start: layers[i].inPoint,
                end: layers[i].outPoint,
                source: layers[i].source || null
            });
        }
        descriptors.sort(function (a, b) { return b.index - a.index; });
        return descriptors;
    }

    function layerFromDescriptor(comp, descriptor) {
        var layer = descriptor.index <= comp.numLayers ? comp.layer(descriptor.index) : null;
        if (layer && layer.name === descriptor.name && layer.source === descriptor.source) { return layer; }
        for (var i = 1; i <= comp.numLayers; i++) {
            layer = comp.layer(i);
            if (layer.name === descriptor.name && layer.source === descriptor.source && Math.abs(layer.inPoint - descriptor.start) < comp.frameDuration * 0.25) { return layer; }
        }
        throw new Error("TonyFX could not relocate selected layer: " + descriptor.name);
    }

    function precomposeDescriptorSeparately(comp, descriptor) {
        var layer = layerFromDescriptor(comp, descriptor);
        var precomp = comp.layers.precompose([layer.index], uniqueItemName(layer.name + " PRECOMP"), true);
        return finishTrimmedPrecomp(comp, precomp, descriptor.start, descriptor.end);
    }

    api.precomposeSelectedSeparately = function () {
        try {
            var comp = activeComp(), layers = selectedLayers(comp).slice(0);
            if (!layers.length) { throw new Error("Select one or more layers to pre-compose separately."); }
            for (var g=0;g<layers.length;g++) { if (isProtected(layers[g])) { throw new Error("Protected or locked layers cannot be pre-composed."); } }
            var descriptors = selectedLayerDescriptors(layers), created = [];
            app.beginUndoGroup("TonyFX Pre-compose Separately");
            for (var d = 1; d <= comp.numLayers; d++) { comp.layer(d).selected = false; }
            for (var i = 0; i < descriptors.length; i++) { created.push(precomposeDescriptorSeparately(comp, descriptors[i])); }
            for (var s = 0; s < created.length; s++) { created[s].selected = true; }
            app.endUndoGroup();
            var result=collectSnapshot(comp);result.message="Pre-composed "+layers.length+" selected layer(s) separately with moved attributes and trimmed durations.";return response(result);
        } catch(error){try{app.endUndoGroup();}catch(ignore){}return response({ok:false,error:error.toString()+(error.line?" at line "+error.line:"")});}
    };

    function configureTwixtorRamp(comp, layer) {
        var effects = layer.property("ADBE Effect Parade");
        if (!effects || !effects.canAddProperty("Twixtor 45")) { throw new Error("Twixtor Pro is unavailable on " + layer.name + "."); }
        for (var e = effects.numProperties; e >= 1; e--) {
            if (effects.property(e).matchName === "Twixtor 45") { effects.property(e).remove(); }
        }
        var twixtor = effects.addProperty("Twixtor 45");
        if (!twixtor) { throw new Error("TonyFX could not add Twixtor Pro to " + layer.name + "."); }
        twixtor.name = "TWIXTOR PRO - EXACT 150 35 150 U-RAMP";
        try { propertyByNames(twixtor, ["Twixtor 45-0009"]).setValue(comp.frameRate); } catch (ignoreFps) {}
        try { propertyByNames(twixtor, ["Twixtor 45-0004"]).setValue(1); } catch (ignoreMode) {}
        try { propertyByNames(twixtor, ["Twixtor 45-0001"]).setValue(3); } catch (ignoreSource) {}
        try { propertyByNames(twixtor, ["Twixtor 45-0044"]).setValue(2); } catch (ignoreEdges) {}
        var speed = propertyByNames(twixtor, ["Twixtor 45-0005", "Speed %", "Speed"]);
        if (!speed) { throw new Error("Twixtor Speed % is unavailable on " + layer.name + "."); }
        var first = layer.inPoint, last = Math.max(first + comp.frameDuration * 2, layer.outPoint - comp.frameDuration), middle = (first + last) / 2;
        clearKeys(speed);
        speed.setValueAtTime(first, 150); speed.setValueAtTime(middle, 35); speed.setValueAtTime(last, 150);
        for (var k = 1; k <= 3; k++) {
            speed.setInterpolationTypeAtKey(k, KeyframeInterpolationType.BEZIER, KeyframeInterpolationType.BEZIER);
            try { speed.setTemporalAutoBezierAtKey(k, false); speed.setTemporalContinuousAtKey(k, false); } catch (ignoreBezier) {}
        }
        speed.setTemporalEaseAtKey(1, [new KeyframeEase(0, 33.333333)], [new KeyframeEase(0, 33.333333)]);
        speed.setTemporalEaseAtKey(2, [new KeyframeEase(-0.24241332631944, 100)], [new KeyframeEase(1.18994407707487, 100)]);
        speed.setTemporalEaseAtKey(3, [new KeyframeEase(0, 33.333333)], [new KeyframeEase(0, 33.333333)]);
        return speed;
    }

    api.applyTwixtorSelected = function () {
        try {
            var comp = activeComp(), layers = selectedLayers(comp).slice(0);
            if (!layers.length) { throw new Error("Select one or more scene layers for Twixtor."); }
            for (var p = 0; p < layers.length; p++) {
                if (isProtected(layers[p])) { throw new Error("Protected or locked layers cannot be changed."); }
                if (!layers[p].source || !layers[p].hasVideo) { throw new Error("Twixtor requires selected video or precomp layers."); }
                var parade = layers[p].property("ADBE Effect Parade");
                if (!parade || !parade.canAddProperty("Twixtor 45")) { throw new Error("Twixtor Pro is not installed or unavailable on " + layers[p].name + "."); }
            }
            var descriptors = selectedLayerDescriptors(layers), processed = [];
            app.beginUndoGroup("TonyFX Twixtor 150 35 150");
            for (var d = 1; d <= comp.numLayers; d++) { comp.layer(d).selected = false; }
            for (var i = 0; i < descriptors.length; i++) {
                var current = layerFromDescriptor(comp, descriptors[i]);
                var outer = current.source instanceof CompItem ? current : precomposeDescriptorSeparately(comp, descriptors[i]);
                configureTwixtorRamp(comp, outer);
                outer.motionBlur = true;
                processed.push(outer);
            }
            for (var s = 0; s < processed.length; s++) { processed[s].selected = true; }
            app.endUndoGroup();
            var result = collectSnapshot(comp); result.message = "Applied precomposed Twixtor 150 / 35 / 150 U-ramps to " + processed.length + " selected scene layer(s)."; return response(result);
        } catch (error) { try { app.endUndoGroup(); } catch (ignore) {} return response({ok:false,error:error.toString() + (error.line ? " at line " + error.line : "")}); }
    };

    api.precomposeSelectedTogether = function () {
        try {
            var comp=activeComp(),layers=selectedLayers(comp).slice(0);
            if(!layers.length){throw new Error("Select two or more layers to pre-compose together.");}
            for(var g=0;g<layers.length;g++){if(isProtected(layers[g])){throw new Error("Protected or locked layers cannot be pre-composed.");}}
            var range=selectedRange(comp,layers),indices=[];for(var i=0;i<layers.length;i++){indices.push(layers[i].index);}indices.sort(function(a,b){return a-b;});
            app.beginUndoGroup("TonyFX Pre-compose Together");
            var precomp=comp.layers.precompose(indices,uniqueItemName("TonyFX Combined PRECOMP"),true);
            finishTrimmedPrecomp(comp,precomp,range.start,range.end);
            app.endUndoGroup();
            var result=collectSnapshot(comp);result.message="Pre-composed "+layers.length+" selected layers together with moved attributes and a trimmed duration.";return response(result);
        } catch(error){try{app.endUndoGroup();}catch(ignore){}return response({ok:false,error:error.toString()+(error.line?" at line "+error.line:"")});}
    };

    api.createAdjustmentForSelection = function () {
        try {
            var comp=activeComp(),layers=selectedLayers(comp),range=selectedRange(comp,layers);
            app.beginUndoGroup("TonyFX Create Adjustment Layer");
            var layer=comp.layers.addSolid([1,1,1],"TonyFX Adjustment Layer",comp.width,comp.height,comp.pixelAspect,comp.duration);
            layer.adjustmentLayer=true;layer.audioEnabled=false;layer.startTime=0;layer.inPoint=range.start;layer.outPoint=range.end;if(range.top){layer.moveBefore(range.top);}layer.selected=true;
            app.endUndoGroup();var result=collectSnapshot(comp);result.message="Created an adjustment layer spanning "+range.start.toFixed(2)+"s to "+range.end.toFixed(2)+"s.";return response(result);
        } catch(error){try{app.endUndoGroup();}catch(ignore){}return response({ok:false,error:error.toString()});}
    };

    api.createNullForSelection = function () {
        try {
            var comp=activeComp(),layers=selectedLayers(comp),range=selectedRange(comp,layers);
            app.beginUndoGroup("TonyFX Create Null");
            var layer=comp.layers.addNull(comp.duration);layer.name="TonyFX Null";layer.startTime=0;layer.inPoint=range.start;layer.outPoint=range.end;if(range.top){layer.moveBefore(range.top);}layer.selected=true;
            app.endUndoGroup();var result=collectSnapshot(comp);result.message="Created a null spanning "+range.start.toFixed(2)+"s to "+range.end.toFixed(2)+"s.";return response(result);
        } catch(error){try{app.endUndoGroup();}catch(ignore){}return response({ok:false,error:error.toString()});}
    };

    api.applyMotionTileSelected = function () {
        try {
            var comp = activeComp();
            var selected = selectedLayers(comp);
            if (!selected.length) { throw new Error("Select scene or footage layers first."); }
            var changed = 0;
            var skipped = 0;
            app.beginUndoGroup("TUF Motion Tile Under Lumetri");
            for (var i = 0; i < selected.length; i++) {
                if (isProtected(selected[i])) { skipped++; continue; }
                var targets = footageTargets(selected[i]);
                for (var t = 0; t < targets.length; t++) {
                    var effects = targets[t].property("ADBE Effect Parade");
                    var lumetri = effectByMatchOrName(effects, "ADBE Lumetri", /lumetri/i);
                    var tile = effectByMatchOrName(effects, "ADBE Tile", /motion tile/i);
                    if (!tile) { tile = effects.addProperty("ADBE Tile"); }
                    setProperty(tile, ["ADBE Tile-0004", "Output Width"], 200);
                    setProperty(tile, ["ADBE Tile-0005", "Output Height"], 200);
                    setProperty(tile, ["ADBE Tile-0011", "Mirror Edges"], true);
                    if (lumetri) {
                        try { lumetri.moveTo(1); } catch (moveLumetriError) {}
                        tile = effectByMatchOrName(effects, "ADBE Tile", /motion tile/i);
                        try { tile.moveTo(2); } catch (moveTileError) {}
                    }
                    changed++;
                }
            }
            app.endUndoGroup();
            var result = collectSnapshot(comp);
            result.message = "Motion Tile 200 reflect applied or corrected on " + changed + " inner footage layer(s)." + (skipped ? " Skipped " + skipped + " protected layer(s)." : "");
            return response(result);
        } catch (error) { try { app.endUndoGroup(); } catch (ignore) {} return response({ok: false, error: error.toString()}); }
    };

    api.applyApprovedOpacitySelected = function () {
        try {
            var comp = activeComp();
            var layers = selectedLayers(comp);
            if (!layers.length) { throw new Error("Select one or more scene layers first."); }
            var changed = 0;
            var skipped = 0;
            app.beginUndoGroup("TUF Approved 45 100 45 Opacity");
            for (var i = 0; i < layers.length; i++) {
                var layer = layers[i];
                if (isProtected(layer)) { skipped++; continue; }
                var opacity = layer.property("ADBE Transform Group").property("ADBE Opacity");
                while (opacity.numKeys) { opacity.removeKey(opacity.numKeys); }
                var start = layer.inPoint;
                var end = Math.max(start + comp.frameDuration * 2, layer.outPoint - comp.frameDuration);
                var middle = start + (end - start) / 2;
                opacity.setValueAtTime(start, 45);
                opacity.setValueAtTime(middle, 100);
                opacity.setValueAtTime(end, 45);
                for (var k = 1; k <= opacity.numKeys; k++) {
                    opacity.setInterpolationTypeAtKey(k, KeyframeInterpolationType.BEZIER, KeyframeInterpolationType.BEZIER);
                    opacity.setTemporalEaseAtKey(k, [new KeyframeEase(0, 72)], [new KeyframeEase(0, 72)]);
                }
                changed++;
            }
            app.endUndoGroup();
            var result = collectSnapshot(comp);
            result.message = "Approved 45 / 100 / 45 opacity arch applied to " + changed + " scene layer(s)." + (skipped ? " Skipped " + skipped + " protected layer(s)." : "");
            return response(result);
        } catch (error) { try { app.endUndoGroup(); } catch (ignore) {} return response({ok: false, error: error.toString()}); }
    };

    api.quickAudit = function () {
        try {
            var result = collectSnapshot(activeComp());
            result.message = "Quick structural audit completed without changes.";
            return response(result);
        } catch (error) { return response({ok: false, error: error.toString()}); }
    };

    api.saveSnapshot = function () {
        try {
            var comp = activeComp();
            var result = collectSnapshot(comp);
            var folder = new Folder(Folder.myDocuments.fsName + "/ae-mcp-bridge");
            if (!folder.exists) { folder.create(); }
            var file = new File(folder.fsName + "/tuf_panel_snapshot.json");
            file.encoding = "UTF-8";
            if (!file.open("w")) { throw new Error("Could not write the snapshot file."); }
            file.write(safeStringify(result));
            file.close();
            result.message = "Snapshot saved to " + file.fsName;
            return response(result);
        } catch (error) { return response({ok: false, error: error.toString()}); }
    };

    function frameTime(comp, frames) { return Math.max(1, Number(frames) || 1) * comp.frameDuration; }

    function easeSpeedArray(value, speed, dimensions) {
        dimensions = dimensions || ((value instanceof Array) ? value.length : 1);
        var result = [];
        for (var i = 0; i < dimensions; i++) {
            var component = speed instanceof Array ? speed[Math.min(i, speed.length - 1)] : speed;
            // AE accepts signed temporal speeds. Preserving the sign is essential
            // for decreasing zoom values; stripping it creates the inverted hump
            // graph that TonyFX must never generate.
            result.push(Number(component) || 0);
        }
        return result;
    }

    function speedBetween(property, firstKey, lastKey, multiplier) {
        var first = property.keyValue(firstKey), last = property.keyValue(lastKey);
        var duration = Math.max(0.0001, property.keyTime(lastKey) - property.keyTime(firstKey));
        var dimensions = first instanceof Array ? first.length : 1, speeds = [];
        for (var i = 0; i < dimensions; i++) {
            var a = first instanceof Array ? first[i] : first;
            var b = last instanceof Array ? last[Math.min(i, last.length - 1)] : last;
            speeds.push((Number(b) - Number(a)) / duration * (Number(multiplier) || 1));
        }
        return speeds;
    }

    function temporalEase(property, keyIndex, inInfluence, outInfluence, inSpeed, outSpeed) {
        var value;
        try { value = property.keyValue(keyIndex); } catch (ignore) { value = 0; }
        var inEase = [], outEase = [];
        var dimensions = (value instanceof Array) ? value.length : 1;
        try {
            if (property.propertyValueType === PropertyValueType.TwoD_SPATIAL || property.propertyValueType === PropertyValueType.ThreeD_SPATIAL) { dimensions = 1; }
        } catch (ignoreValueType) {}
        var incoming = easeSpeedArray(value, inSpeed || 0, dimensions), outgoing = easeSpeedArray(value, outSpeed || 0, dimensions);
        for (var i = 0; i < incoming.length; i++) {
            inEase.push(new KeyframeEase(incoming[i], Math.max(0.1, Math.min(100, inInfluence))));
            outEase.push(new KeyframeEase(outgoing[i], Math.max(0.1, Math.min(100, outInfluence))));
        }
        property.setInterpolationTypeAtKey(keyIndex, KeyframeInterpolationType.BEZIER, KeyframeInterpolationType.BEZIER);
        property.setTemporalEaseAtKey(keyIndex, inEase, outEase);
    }

    function easeFastStart(property, firstKey, lastKey) {
        var speed = speedBetween(property, firstKey, lastKey, 1.85);
        temporalEase(property, firstKey, 18, 58, 0, speed);
        temporalEase(property, lastKey, 84, 18, 0, 0);
    }

    function easeFastEnd(property, firstKey, lastKey) {
        var speed = speedBetween(property, firstKey, lastKey, 1.85);
        temporalEase(property, firstKey, 18, 84, 0, 0);
        temporalEase(property, lastKey, 58, 18, speed, 0);
    }

    function easeCleanInOut(property, firstKey, lastKey) {
        temporalEase(property, firstKey, 22, 72, 0, 0);
        temporalEase(property, lastKey, 72, 22, 0, 0);
    }

    function easyEaseKey(property, keyIndex) {
        temporalEase(property, keyIndex, 33.333, 33.333, 0, 0);
    }

    function easyEaseAll(property) {
        if (!property) { return; }
        for (var i = 1; i <= property.numKeys; i++) { easyEaseKey(property, i); }
    }

    function easeApprovedRamp(property, firstKey, lastKey) {
        var speed = speedBetween(property, firstKey, lastKey, 2.05);
        temporalEase(property, firstKey, 16, 52, 0, speed);
        temporalEase(property, lastKey, 52, 16, speed, 0);
    }

    function easeCustomBezier(property, firstKey, lastKey, controls) {
        controls = controls || [0.25, 0.25, 0.75, 0.75];
        var x1 = Math.max(0.001, Math.min(0.999, Number(controls[0]) || 0.25));
        var y1 = Math.max(-2, Math.min(3, Number(controls[1]) || 0));
        var x2 = Math.max(0.001, Math.min(0.999, Number(controls[2]) || 0.75));
        var y2 = Math.max(-2, Math.min(3, Number(controls[3]) || 1));
        var averageSpeed = speedBetween(property, firstKey, lastKey, 1);
        var outgoingSpeed = [];
        var incomingSpeed = [];
        for (var i = 0; i < averageSpeed.length; i++) {
            outgoingSpeed.push(averageSpeed[i] * (y1 / x1));
            incomingSpeed.push(averageSpeed[i] * ((1 - y2) / Math.max(0.001, 1 - x2)));
        }
        temporalEase(property, firstKey, 16, Math.max(0.1, x1 * 100), 0, outgoingSpeed);
        temporalEase(property, lastKey, Math.max(0.1, (1 - x2) * 100), 16, incomingSpeed, 0);
    }

    function easeTonyFXShotRamp(property, firstKey, lastKey) {
        // Locked BlurMoCurves ramp taught by TUF: 0.09, 0.72, 0.94, 0.27.
        // Shot-motion curves detected in a reference are evidence, not safe AE
        // tangents. Keep their direction/value range, but always use this ramp.
        var averageSpeed = speedBetween(property, firstKey, lastKey, 1);
        var outgoingSpeed = [], incomingSpeed = [];
        for (var i = 0; i < averageSpeed.length; i++) {
            outgoingSpeed.push(averageSpeed[i] * (0.72 / 0.09));
            incomingSpeed.push(averageSpeed[i] * ((1 - 0.27) / (1 - 0.94)));
        }
        temporalEase(property, firstKey, 16, 9, 0, outgoingSpeed);
        temporalEase(property, lastKey, 6, 16, incomingSpeed, 0);
        try {
            property.setTemporalContinuousAtKey(firstKey, false);
            property.setTemporalContinuousAtKey(lastKey, false);
            property.setTemporalAutoBezierAtKey(firstKey, false);
            property.setTemporalAutoBezierAtKey(lastKey, false);
        } catch (ignoreRampFlags) {}
    }

    function clearKeys(property) {
        while (property && property.numKeys) { property.removeKey(property.numKeys); }
    }

    function offsetFor(direction, amount) {
        if (direction === "left") { return [-amount, 0]; }
        if (direction === "right") { return [amount, 0]; }
        if (direction === "up") { return [0, -amount]; }
        return [0, amount];
    }

    function addValues(base, offset) {
        var result = base.slice(0);
        result[0] += offset[0]; result[1] += offset[1];
        return result;
    }

    function removeNamedProperty(group, name) {
        if (!group || !name) { return; }
        for (var i = group.numProperties; i >= 1; i--) {
            var property = group.property(i);
            if (property && property.name === name) { try { property.remove(); } catch (ignore) {} }
        }
    }

    function applyLayerMotion(comp, layer, options, layerIndex) {
        var effects = layer.property("ADBE Effect Parade"), effectName = "TonyFX - " + options.name;
        removeNamedProperty(effects, effectName);
        var transform = addTransformEffect(effects, effectName, comp);
        if (!transform) { return false; }
        var staggerFrames = Number(options.stagger) || 0;
        var start = Math.max(layer.inPoint, comp.time + Math.max(0, staggerFrames) * comp.frameDuration * layerIndex);
        var end = Math.min(layer.outPoint - comp.frameDuration, start + frameTime(comp, options.duration || 6));
        if (end <= start) { return false; }
        if (options.mode === "scale" || options.mode === "punchIn" || options.mode === "punchOut" || options.mode === "spin" || options.mode === "focusPush") {
            var scaleHeight = propertyByNamesOrIndex(transform, ["Scale", "Scale Height"], 4);
            var scaleWidth = propertyByNames(transform, ["Scale Width"]), scaleProps = [scaleHeight, scaleWidth];
            for (var sp = 0; sp < scaleProps.length; sp++) {
                var scale = scaleProps[sp];
                if (!scale || (sp === 1 && scale === scaleHeight)) { continue; }
                clearKeys(scale);
                if (options.mode === "punchIn") {
                    scale.setValueAtTime(start, 62); scale.setValueAtTime(start + (end - start) * 0.68, 114); scale.setValueAtTime(end, 100);
                } else if (options.mode === "punchOut") {
                    scale.setValueAtTime(start, 168); scale.setValueAtTime(start + (end - start) * 0.72, 92); scale.setValueAtTime(end, 100);
                } else if (options.mode === "spin") {
                    scale.setValueAtTime(start, 46); scale.setValueAtTime(start + (end - start) * 0.72, 108); scale.setValueAtTime(end, 100);
                } else if (options.mode === "focusPush") {
                    scale.setValueAtTime(start, 132); scale.setValueAtTime(end, 100);
                } else {
                    scale.setValueAtTime(start, 0); scale.setValueAtTime(start + (end - start) * 0.625, 215); scale.setValueAtTime(end, 100);
                }
                easyEaseAll(scale);
            }
            if (options.mode === "spin") {
                var spinRotation = propertyByNames(transform, ["Rotation"]);
                if (spinRotation) { clearKeys(spinRotation); spinRotation.setValueAtTime(start, -92); spinRotation.setValueAtTime(end, 0); easyEaseAll(spinRotation); }
            }
            if (options.mode === "focusPush") {
                var focusBlur = addEffectSafe(effects, "ADBE Gaussian Blur 2", effectName + " Blur");
                if (focusBlur) {
                    var focusAmount = propertyByNamesOrIndex(focusBlur, ["Blurriness", "ADBE Gaussian Blur 2-0001"], 1);
                    clearKeys(focusAmount); focusAmount.setValueAtTime(start, 38); focusAmount.setValueAtTime(end, 0); easyEaseAll(focusAmount);
                    setProperty(focusBlur, ["Repeat Edge Pixels", "ADBE Gaussian Blur 2-0003"], true);
                }
            }
            layer.motionBlur = true; return true;
        }
        if (options.mode === "rotate") {
            var rotation = propertyByNames(transform, ["Rotation"]);
            if (!rotation) { return false; }
            clearKeys(rotation); rotation.setValueAtTime(start, -(Number(options.amount) || 22)); rotation.setValueAtTime(start + (end - start) * 0.72, 4); rotation.setValueAtTime(end, 0); easyEaseAll(rotation);
            layer.motionBlur = true; return true;
        }
        var position = propertyByNamesOrIndex(transform, ["Position"], 2);
        var targetPosition = [comp.width / 2, comp.height / 2];
        var direction = options.direction || "left";
        var axisSize = (direction === "left" || direction === "right") ? comp.width : comp.height;
        var minimumDistance = (options.mode === "drift" || options.mode === "float" || options.mode === "fadeRise") ? axisSize * 0.12 : axisSize * 1.08;
        var offset = offsetFor(direction, Math.max(Number(options.amount) || 0, minimumDistance));
        var startPosition = addValues(targetPosition, offset);
        clearKeys(position); position.setValueAtTime(start, startPosition);
        if (options.mode === "drop") {
            position.setValueAtTime(start + (end - start) * 0.66, addValues(targetPosition, [0, -Math.abs(offset[1]) * 0.16]));
            position.setValueAtTime(start + (end - start) * 0.84, addValues(targetPosition, [0, Math.abs(offset[1]) * 0.06]));
        } else if (options.variant === "overshoot") {
            position.setValueAtTime(start + (end - start) * 0.68, addValues(targetPosition, [-offset[0] * 0.14, -offset[1] * 0.14]));
        } else if (options.variant === "bounce") {
            position.setValueAtTime(start + (end - start) * 0.58, addValues(targetPosition, [-offset[0] * 0.18, -offset[1] * 0.18]));
            position.setValueAtTime(start + (end - start) * 0.82, addValues(targetPosition, [offset[0] * 0.07, offset[1] * 0.07]));
        }
        position.setValueAtTime(end, targetPosition);
        easyEaseAll(position);
        if (options.mode === "fadeRise") {
            var layerOpacity = layer.property("ADBE Transform Group").property("ADBE Opacity");
            clearKeys(layerOpacity); layerOpacity.setValueAtTime(start, 0); layerOpacity.setValueAtTime(end, 100); easyEaseAll(layerOpacity);
        }
        layer.motionBlur = true; return true;
    }

    function textUnitValue(unit) {
        if (unit === "words") { return 3; }
        if (unit === "lines") { return 4; }
        return 2;
    }

    var TONYFX_LEGACY_TEXT_MOTIONS = {
        "Text Reveal Left":true,"Text Reveal Right":true,"Text Reveal Up":true,"Text Reveal Down":true,
        "Letter Fade":true,"Word Fade":true,"Word Scale Pop":true,"Letter Rotate In":true,
        "Blur Reveal":true,"Tracking Reveal":true,"Soft Word Rise":true,"Word Drop In":true,
        "Pop + Focus":true,"Scale Punch":true,"Word Rotate In":true,"Tracking Tighten":true,
        "Clean Wipe Left":true,"Clean Wipe Right":true,"Flicker On":true,"Wave Rise":true
    };

    function removeTonyFxTextMotion(layer, includeCaption) {
        var text = layer.property("ADBE Text Properties");
        var animators = text && text.property("ADBE Text Animators");
        if (!animators) { return; }
        for (var i = animators.numProperties; i >= 1; i--) {
            var animator = animators.property(i), name = String(animator.name || ""), remove = false;
            if (name.indexOf("TonyFX - Text Motion - ") === 0 || name.indexOf("TUF - Text Motion - ") === 0) { remove = true; }
            if (name.indexOf("TonyFX - ") === 0 && TONYFX_LEGACY_TEXT_MOTIONS[name.substring(9)]) { remove = true; }
            if (name.indexOf("TUF - ") === 0 && TONYFX_LEGACY_TEXT_MOTIONS[name.substring(6)]) { remove = true; }
            if (includeCaption && name === "TonyFX - Caption Reveal") { remove = true; }
            if (remove) { try { animator.remove(); } catch (ignoreRemoveTextMotion) {} }
        }
    }

    function textMotionSpec(options) {
        var id = String(options.id || ""), mode = String(options.mode || "opacity");
        var spec = {
            id:id,
            name:String(options.name || id || "Text Motion"),
            unit:String(options.unit || "characters"),
            duration:Math.max(10, Number(options.duration) || 18),
            smoothness:Number(options.smoothness),
            easeHigh:68,
            easeLow:68,
            driver:"start",
            opacity:undefined,
            position:null,
            scale:null,
            rotationX:undefined,
            rotationY:undefined,
            rotationZ:undefined,
            blur:undefined,
            tracking:undefined,
            perCharacter3D:false,
            flicker:false,
            wordSync:false,
            accent:null
        };
        if (!isFinite(spec.smoothness)) { spec.smoothness = spec.unit === "words" ? 32 : 18; }

        if (id === "text-left" || id === "text-right" || id === "text-up" || id === "text-down" || mode === "position") {
            var direction = options.direction || (id === "text-right" ? "right" : id === "text-up" ? "up" : id === "text-down" ? "down" : "left");
            // Text motion must read clearly at 1080 social-video scale. Earlier
            // recipes inherited tiny UI-preview distances (48-96 px), which
            // made distinct presets look like the same faint opacity reveal.
            var amount = Math.max(
                (direction === "left" || direction === "right") ? 420 : 260,
                Number(options.amount) || 0
            );
            var movement = offsetFor(direction, amount);
            spec.position = [movement[0], movement[1], 0]; spec.opacity = 0; spec.blur = 18; spec.unit = options.unit || "words";
            spec.smoothness = id === "text-soft-rise" ? 42 : 22;
            if (direction === "left") { spec.accent={position:[34,0,0],peak:0.72}; }
            if (direction === "right") { spec.accent={position:[-34,0,0],peak:0.72}; }
            if (direction === "up") { spec.accent={position:[0,28,0],peak:0.72}; }
            if (direction === "down") { spec.accent={position:[0,-28,0],peak:0.72}; }
            if (id === "text-soft-rise") { spec.position = [0, 160, 0]; spec.blur = 16; spec.duration = Math.max(spec.duration, 12); spec.easeHigh = 82; spec.easeLow = 54; spec.accent={position:[0,-18,0],peak:0.74}; }
            if (id === "text-drop-in") { spec.position = [0, -300, 0]; spec.rotationZ = -9; spec.blur = 20; spec.smoothness = 14; spec.easeHigh = 48; spec.easeLow = 82; spec.accent={position:[0,38,0],peak:0.76}; }
        } else if (id === "text-scale-pop" || mode === "scale") {
            spec.unit = "words"; spec.scale = [6,6,100]; spec.opacity = 0; spec.blur = 24; spec.smoothness = 14; spec.easeHigh = 42; spec.easeLow = 84;
            spec.accent={scale:[152,152,100],peak:0.70};
        } else if (id === "text-rotate" || id === "text-rotate-words" || mode === "rotate") {
            spec.unit = id === "text-rotate-words" ? "words" : (options.unit || "characters");
            spec.rotationZ = id === "text-rotate-words" ? -72 : -145;
            spec.position = id === "text-rotate-words" ? [0,140,0] : [0,100,0];
            spec.scale = id === "text-rotate-words" ? [34,34,100] : null;
            spec.blur = 18; spec.opacity = 0; spec.smoothness = spec.unit === "words" ? 18 : 8;
            if (id === "text-rotate-words") { spec.accent={rotationZ:7,peak:0.78}; }
        } else if (id === "text-blur-reveal" || mode === "blur") {
            spec.unit = options.unit || "words"; spec.blur = 92; spec.position = [0,90,0]; spec.scale=[132,132,100]; spec.opacity = 0; spec.smoothness = 30;
        } else if (id === "text-pop-blur" || mode === "popBlur") {
            spec.unit = "words"; spec.scale = [4,4,100]; spec.blur = 96; spec.position = [0,64,0]; spec.opacity = 0; spec.smoothness = 12;
            spec.accent={scale:[162,162,100],peak:0.68};
        } else if (id === "text-scale-punch" || mode === "scalePunch") {
            spec.unit = "words"; spec.scale = [238,238,100]; spec.blur = 26; spec.opacity = 0; spec.smoothness = 10; spec.easeHigh = 42; spec.easeLow = 88;
            spec.accent={scale:[126,126,100],peak:0.76};
        } else if (id === "text-tracking-reveal" || mode === "tracking") {
            spec.unit = "characters"; spec.tracking = 420; spec.blur = 24; spec.opacity = 0; spec.smoothness = 18;
        } else if (id === "text-tighten" || mode === "trackingTight") {
            spec.unit = "characters"; spec.tracking = 520; spec.blur = 30; spec.opacity = 0; spec.smoothness = 22; spec.duration = Math.max(spec.duration, 14);
        } else if (id === "text-wipe-left" || id === "text-wipe-right" || mode === "wipe") {
            var wipeRight = id === "text-wipe-right" || options.direction === "right";
            spec.unit = "characters"; spec.position = [wipeRight ? 480 : -480,0,0]; spec.blur=26; spec.opacity = 0;
            spec.smoothness = 4; spec.easeHigh = 26; spec.easeLow = 84; spec.driver = wipeRight ? "end" : "start";
        } else if (id === "text-wave-rise" || mode === "wave") {
            spec.unit = "characters"; spec.position = [0,220,0]; spec.rotationZ = -32; spec.blur = 22; spec.opacity = 0;
            spec.smoothness = 38; spec.duration = Math.max(spec.duration, 16); spec.easeHigh = 78; spec.easeLow = 56;
        } else if (id === "text-flicker-on" || mode === "flicker") {
            spec.unit = "characters"; spec.opacity = 0; spec.smoothness = 0; spec.flicker = true; spec.driver = "amount";
        } else {
            spec.opacity = 0;
            spec.unit = id === "text-word-fade" ? "words" : (options.unit || "characters");
            spec.smoothness = id === "text-word-fade" ? 62 : 22;
        }
        return spec;
    }

    function addTextMotionAccent(comp, layer, spec, start, end) {
        if (!spec.accent) { return; }
        var text = layer.property("ADBE Text Properties"), animators = text && text.property("ADBE Text Animators");
        if (!animators || !animators.canAddProperty("ADBE Text Animator")) { return; }
        var animator = animators.addProperty("ADBE Text Animator");
        animator.name = "TonyFX - Text Motion - " + spec.name + " - Settle";
        var props=animator.property("ADBE Text Animator Properties"), accent=spec.accent;
        if (accent.position) { addTextFxProperty(props,"ADBE Text Position 3D",accent.position); }
        if (accent.scale) { addTextFxProperty(props,"ADBE Text Scale 3D",accent.scale); }
        if (accent.rotationZ !== undefined) { addTextFxProperty(props,"ADBE Text Rotation",accent.rotationZ); }
        var selector=animator.property("ADBE Text Selectors").addProperty("ADBE Text Selector");
        var advanced=selector.property("ADBE Text Range Advanced");
        var amount=advanced && captionSelectorProperty(advanced,["ADBE Text Selector Max Amount","Amount"]);
        if (!amount) { return; }
        clearKeys(amount);
        var peak=Math.max(0.55,Math.min(0.9,Number(accent.peak)||0.72));
        var accentStart=Math.max(start,end-Math.max(comp.frameDuration*5,(end-start)*0.42));
        var peakTime=accentStart+(end-accentStart)*peak;
        amount.setValueAtTime(accentStart,0);
        amount.setValueAtTime(peakTime,100);
        amount.setValueAtTime(end,0);
        easyEaseAll(amount);
    }

    function setTextSelectorAdvanced(advanced, spec) {
        if (!advanced) { return; }
        try { advanced.property("ADBE Text Range Type2").setValue(textUnitValue(spec.unit)); } catch (ignoreBasedOn) {}
        try { advanced.property("ADBE Text Range Shape").setValue(1); } catch (ignoreShape) {}
        try { advanced.property("ADBE Text Selector Smoothness").setValue(Math.max(0,Math.min(100,spec.smoothness))); } catch (ignoreSmoothness) {}
        try { advanced.property("ADBE Text Levels Max Ease").setValue(Math.max(-100,Math.min(100,spec.easeHigh))); } catch (ignoreEaseHigh) {}
        try { advanced.property("ADBE Text Levels Min Ease").setValue(Math.max(-100,Math.min(100,spec.easeLow))); } catch (ignoreEaseLow) {}
        try { advanced.property("ADBE Text Randomize Order").setValue(false); } catch (ignoreRandomOrder) {}
    }

    function buildTextMotionAnimator(comp, layer, spec, start, end, words) {
        var text = layer.property("ADBE Text Properties"), animators = text && text.property("ADBE Text Animators");
        if (!animators || !animators.canAddProperty("ADBE Text Animator")) { return false; }
        var animator = animators.addProperty("ADBE Text Animator");
        animator.name = "TonyFX - Text Motion - " + spec.name + " - IN";
        var props = animator.property("ADBE Text Animator Properties");
        if (spec.opacity !== undefined) { addTextFxProperty(props,"ADBE Text Opacity",spec.opacity); }
        if (spec.position) { addTextFxProperty(props,"ADBE Text Position 3D",spec.position); }
        if (spec.scale) { addTextFxProperty(props,"ADBE Text Scale 3D",spec.scale); }
        if (spec.rotationX !== undefined) { addTextFxProperty(props,"ADBE Text Rotation X",spec.rotationX); }
        if (spec.rotationY !== undefined) { addTextFxProperty(props,"ADBE Text Rotation Y",spec.rotationY); }
        if (spec.rotationZ !== undefined) { addTextFxProperty(props,"ADBE Text Rotation",spec.rotationZ); }
        if (spec.blur !== undefined) { addTextFxProperty(props,"ADBE Text Blur",[spec.blur,spec.blur]); }
        if (spec.tracking !== undefined) { addTextFxProperty(props,"ADBE Text Tracking Amount",spec.tracking); }
        if (spec.perCharacter3D) { try { layer.threeDPerChar = true; } catch (ignorePerCharacter3D) {} }

        var selector = animator.property("ADBE Text Selectors").addProperty("ADBE Text Selector");
        var advanced = selector.property("ADBE Text Range Advanced");
        setTextSelectorAdvanced(advanced,spec);
        var startProp = captionSelectorProperty(selector,["ADBE Text Percent Start","ADBE Text Selector Start","Start"]);
        var endProp = captionSelectorProperty(selector,["ADBE Text Percent End","ADBE Text Selector End","End"]);
        if (!startProp || !endProp) { animator.remove(); throw new Error("TonyFX could not access the text range selector."); }
        clearKeys(startProp); clearKeys(endProp); startProp.setValue(0); endProp.setValue(100);

        if (spec.flicker) {
            var amount = advanced && captionSelectorProperty(advanced,["ADBE Text Selector Max Amount","Amount"]);
            if (!amount) { amount = startProp; }
            clearKeys(amount);
            var span = Math.max(comp.frameDuration * 5,end-start), steps = [100,0,78,0,44,0];
            for (var f=0; f<steps.length; f++) { amount.setValueAtTime(Math.min(end,start + span * f/(steps.length-1)),steps[f]); }
            for (var fk=1; fk<=amount.numKeys; fk++) { try { amount.setInterpolationTypeAtKey(fk,KeyframeInterpolationType.HOLD,KeyframeInterpolationType.HOLD); } catch (ignoreFlickerHold) {} }
        } else if (spec.wordSync && words && words.length && spec.driver === "start" && revealCaptionWords(comp,startProp,words,start,end)) {
            // Word timestamps drive the same selector used by manual presets.
        } else if (spec.driver === "end") {
            endProp.setValueAtTime(start,100); endProp.setValueAtTime(end,0); easyEaseAll(endProp);
        } else {
            startProp.setValueAtTime(start,0); startProp.setValueAtTime(end,100); easyEaseAll(startProp);
        }
        addTextMotionAccent(comp,layer,spec,start,end);
        layer.motionBlur = true;
        return true;
    }

    function buildTextMotionExitAnimator(comp, layer, spec, start, end) {
        var text = layer.property("ADBE Text Properties"), animators = text && text.property("ADBE Text Animators");
        if (!animators || !animators.canAddProperty("ADBE Text Animator") || end <= start) { return false; }
        var animator = animators.addProperty("ADBE Text Animator");
        animator.name = "TonyFX - Text Motion - " + spec.name + " - OUT";
        var props = animator.property("ADBE Text Animator Properties");
        if (spec.opacity !== undefined) { addTextFxProperty(props,"ADBE Text Opacity",spec.opacity); }
        if (spec.position) { addTextFxProperty(props,"ADBE Text Position 3D",spec.position); }
        if (spec.scale) { addTextFxProperty(props,"ADBE Text Scale 3D",spec.scale); }
        if (spec.rotationX !== undefined) { addTextFxProperty(props,"ADBE Text Rotation X",spec.rotationX); }
        if (spec.rotationY !== undefined) { addTextFxProperty(props,"ADBE Text Rotation Y",spec.rotationY); }
        if (spec.rotationZ !== undefined) { addTextFxProperty(props,"ADBE Text Rotation",spec.rotationZ); }
        if (spec.blur !== undefined) { addTextFxProperty(props,"ADBE Text Blur",[spec.blur,spec.blur]); }
        if (spec.tracking !== undefined) { addTextFxProperty(props,"ADBE Text Tracking Amount",spec.tracking); }
        if (spec.perCharacter3D) { try { layer.threeDPerChar = true; } catch (ignoreExit3D) {} }
        var selector = animator.property("ADBE Text Selectors").addProperty("ADBE Text Selector");
        var advanced = selector.property("ADBE Text Range Advanced");
        setTextSelectorAdvanced(advanced,spec);
        var startProp = captionSelectorProperty(selector,["ADBE Text Percent Start","ADBE Text Selector Start","Start"]);
        var endProp = captionSelectorProperty(selector,["ADBE Text Percent End","ADBE Text Selector End","End"]);
        if (!startProp || !endProp) { animator.remove(); return false; }
        clearKeys(startProp); clearKeys(endProp); startProp.setValue(0);
        endProp.setValueAtTime(start,0); endProp.setValueAtTime(end,100); easyEaseAll(endProp);
        return true;
    }

    function addMatchedTextExit(comp, layer, spec, entryEnd, options) {
        if (options && options.matchedExit === false) { return false; }
        var exitFrames = Math.max(6, Number(options && options.exitDuration) || Math.max(12,spec.duration));
        var exitEnd = layer.outPoint - comp.frameDuration;
        var exitStart = Math.max(entryEnd + comp.frameDuration, exitEnd - frameTime(comp,exitFrames));
        if (exitEnd <= exitStart) { return false; }
        return buildTextMotionExitAnimator(comp,layer,spec,exitStart,exitEnd);
    }

    function applyTextMotion(comp, layer, options, layerIndex) {
        var text = layer.property("ADBE Text Properties");
        if (!text || !text.property("ADBE Text Document")) { return false; }
        var textStagger = Math.max(0, Number(options.stagger) || 0);
        var start = layer.inPoint + textStagger * comp.frameDuration * layerIndex;
        var end = Math.min(layer.outPoint - comp.frameDuration, start + frameTime(comp, options.duration || 10));
        if (end <= start) { return false; }
        removeTonyFxTextMotion(layer,true);
        var spec = textMotionSpec(options);
        var built = buildTextMotionAnimator(comp,layer,spec,start,end,null);
        if (built) { addMatchedTextExit(comp,layer,spec,end,options); }
        return built;
    }

    function applyEaseToSelection(comp, options) {
        var properties = comp.selectedProperties || [];
        var changed = 0;
        for (var i = 0; i < properties.length; i++) {
            var property = properties[i];
            if (!(property instanceof Property) || !property.selectedKeys || !property.selectedKeys.length) { continue; }
            var keys = property.selectedKeys.slice(0).sort(function (a, b) { return a - b; });
            if (options.curve === "linear") {
                for (var k = 0; k < keys.length; k++) { property.setInterpolationTypeAtKey(keys[k], KeyframeInterpolationType.LINEAR, KeyframeInterpolationType.LINEAR); }
            } else if (keys.length >= 2 && options.curve === "sharpStart") {
                easeFastStart(property, keys[0], keys[keys.length - 1]);
            } else if (keys.length >= 2 && options.curve === "sharpEnd") {
                easeFastEnd(property, keys[0], keys[keys.length - 1]);
            } else if (keys.length >= 2 && options.curve === "approvedRamp") {
                easeApprovedRamp(property, keys[0], keys[keys.length - 1]);
            } else if (keys.length >= 2 && options.curve === "customBezier") {
                easeCustomBezier(property, keys[0], keys[keys.length - 1], options.bezier || options.controls);
            } else if (keys.length >= 2) {
                easeCleanInOut(property, keys[0], keys[keys.length - 1]);
            } else {
                temporalEase(property, keys[0], 66, 66);
            }
            changed += keys.length;
        }
        if (!changed) { throw new Error("Select keyframes in the Timeline or Graph Editor first."); }
        return changed;
    }

    function addEffectSafe(effects, matchName, displayName) {
        var effect = null;
        removeNamedProperty(effects, displayName);
        try { effect = effects.addProperty(matchName); } catch (ignore) {}
        if (effect && displayName) { effect.name = displayName; }
        return effect;
    }

    function animateThree(property, start, middle, end, first, peak, last) {
        if (!property) { return false; }
        clearKeys(property);
        property.setValueAtTime(start, first);
        property.setValueAtTime(middle, peak);
        property.setValueAtTime(end, last);
        easeFastStart(property, 1, 2);
        easeFastEnd(property, 2, 3);
        return true;
    }

    function animateImpact(property, start, end, peak, settled) {
        if (!property) { return false; }
        clearKeys(property);
        property.setValueAtTime(start, peak);
        property.setValueAtTime(end, settled);
        easeFastStart(property, 1, 2);
        return true;
    }

    function collectKeyRange(group, range) {
        if (!group) { return range; }
        if (group instanceof Property) {
            if (group.numKeys) {
                range.first = Math.min(range.first, group.keyTime(1));
                range.last = Math.max(range.last, group.keyTime(group.numKeys));
            }
            return range;
        }
        for (var i = 1; i <= group.numProperties; i++) { collectKeyRange(group.property(i), range); }
        return range;
    }

    function trimAdjustmentToAnimation(layer, fallbackIn, fallbackOut) {
        var range = collectKeyRange(layer.property("ADBE Effect Parade"), {first:999999,last:-999999});
        var start = range.last >= range.first ? range.first : fallbackIn;
        var end = range.last >= range.first ? range.last : fallbackOut;
        layer.inPoint = Math.max(0, start);
        layer.outPoint = Math.min(layer.containingComp.duration, Math.max(layer.inPoint + layer.containingComp.frameDuration, end));
        return layer;
    }

    function addTransformEffect(effects, name, comp) {
        var transform = addEffectSafe(effects, "ADBE Geometry2", name);
        if (!transform) { return null; }
        setProperty(transform, ["Anchor Point"], [comp.width / 2, comp.height / 2]);
        setProperty(transform, ["Uniform Scale"], true);
        setProperty(transform, ["Use Composition's Shutter Angle", "Use Comp's Shutter Angle"], false);
        setProperty(transform, ["Shutter Angle"], 360);
        return transform;
    }

    function safeLayerName(name) {
        return String(name || "Scene").replace(/[\\\/:*?\"<>|]/g, " ").replace(/\s+/g, " ");
    }

    function createEffectAdjustment(comp, presetName, inPoint, outPoint, aboveLayer) {
        var name = "TonyFX FX - " + safeLayerName(presetName) + " - " + safeLayerName(aboveLayer ? aboveLayer.name : "Cut");
        for (var i = comp.numLayers; i >= 1; i--) {
            if (comp.layer(i).name === name) { comp.layer(i).remove(); }
        }
        var layer = comp.layers.addSolid([1, 1, 1], name, comp.width, comp.height, comp.pixelAspect, comp.duration);
        layer.adjustmentLayer = true;
        layer.audioEnabled = false;
        layer.startTime = 0;
        layer.inPoint = Math.max(0, inPoint);
        layer.outPoint = Math.min(comp.duration, Math.max(layer.inPoint + comp.frameDuration, outPoint));
        if (aboveLayer) { layer.moveBefore(aboveLayer); }
        layer.label = 13;
        return layer;
    }

    function animateEffectShake(transform, comp, t, frames, amount) {
        var position = propertyByNamesOrIndex(transform, ["Position"], 2);
        if (!position) { return false; }
        var fd = comp.frameDuration, center = [comp.width / 2, comp.height / 2], strength = Math.max(10, amount * 0.2);
        clearKeys(position);
        position.setValueAtTime(t, center);
        position.setValueAtTime(t + fd, [center[0] + strength, center[1] - strength * 0.55]);
        position.setValueAtTime(t + fd * 2, [center[0] - strength * 0.58, center[1] + strength * 0.34]);
        position.setValueAtTime(t + fd * Math.max(3, frames), center);
        for (var i = 1; i <= position.numKeys; i++) { temporalEase(position, i, i === position.numKeys ? 86 : 45, i === 1 ? 86 : 45); }
        return true;
    }

    function applyWhipSide(comp, layer, name, start, end, fromPosition, toPosition, blurFrom, blurTo, sharpArrival) {
        var effects = layer.property("ADBE Effect Parade");
        var transform = addTransformEffect(effects, name, comp);
        if (!transform) { return false; }
        var position = propertyByNamesOrIndex(transform, ["Position"], 2);
        clearKeys(position);
        position.setValueAtTime(start, fromPosition);
        position.setValueAtTime(end, toPosition);
        if (sharpArrival) {
            temporalEase(position, 1, 82, 18); temporalEase(position, 2, 88, 14);
        } else {
            temporalEase(position, 1, 14, 88); temporalEase(position, 2, 18, 82);
        }
        var blur = addEffectSafe(effects, "ADBE Motion Blur", name + " Blur");
        if (blur) {
            setProperty(blur, ["ADBE Motion Blur-0001", "Direction"], 0);
            var length = propertyByNamesOrIndex(blur, ["ADBE Motion Blur-0002", "Blur Length"], 2);
            clearKeys(length);
            length.setValueAtTime(start, blurFrom);
            length.setValueAtTime(end, blurTo);
            temporalEase(length, 1, sharpArrival ? 82 : 14, sharpArrival ? 18 : 88);
            temporalEase(length, 2, sharpArrival ? 88 : 18, sharpArrival ? 14 : 82);
        }
        return true;
    }

    function applyPairedWhip(comp, layers, options) {
        if (layers.length < 1 || layers.length > 2) { throw new Error("Select one scene at the playhead or two adjacent scene layers for a paired whip."); }
        layers.sort(function (a, b) { return a.inPoint - b.inPoint; });
        var outgoing = layers[0], incoming = layers.length === 2 ? layers[1] : layers[0];
        if (isProtected(outgoing) || isProtected(incoming)) { throw new Error("The selected whip layers cannot be protected or locked."); }
        var cut = layers.length === 2 ? incoming.inPoint : Math.max(outgoing.inPoint + comp.frameDuration * 2, Math.min(comp.time, outgoing.outPoint - comp.frameDuration * 2));
        var fd = comp.frameDuration, frames = Math.max(3, Math.min(10, Number(options.duration) || 6));
        var span = frames * fd, outStart = Math.max(outgoing.inPoint, cut - span), outEnd = Math.min(outgoing.outPoint - fd, cut);
        var inStart = Math.max(incoming.inPoint, cut), inEnd = Math.min(incoming.outPoint - fd, cut + span);
        if (outEnd <= outStart || inEnd <= inStart) { throw new Error("The selected layers need enough frames around their cut for this whip."); }
        var adjustment = createEffectAdjustment(comp, options.name, outStart, inEnd, outgoing);
        var effects = adjustment.property("ADBE Effect Parade");
        var center = [comp.width / 2, comp.height / 2], sign = options.direction === "left" ? -1 : 1;
        var distance = Math.max(comp.width * 0.48, Number(options.amount) * 3.2), blur = Math.max(58, Number(options.amount) * 0.75);
        var transform = addTransformEffect(effects, "TonyFX - Whip Transform", comp);
        var position = propertyByNamesOrIndex(transform, ["Position"], 2);
        clearKeys(position);
        position.setValueAtTime(outStart, center);
        position.setValueAtTime(outEnd, [center[0] + sign * distance, center[1]]);
        position.setValueAtTime(inStart + fd * 0.25, [center[0] - sign * distance, center[1]]);
        position.setValueAtTime(inEnd, center);
        easeFastStart(position, 1, 2); easeFastEnd(position, 3, 4);
        var motionBlur = addEffectSafe(effects, "ADBE Motion Blur", "TonyFX - Whip Directional Blur");
        if (motionBlur) {
            setProperty(motionBlur, ["ADBE Motion Blur-0001", "Direction"], 0);
            var blurLength = propertyByNamesOrIndex(motionBlur, ["ADBE Motion Blur-0002", "Blur Length"], 2);
            clearKeys(blurLength);
            blurLength.setValueAtTime(outStart, 4); blurLength.setValueAtTime(cut, blur); blurLength.setValueAtTime(inEnd, 4);
            easeFastStart(blurLength, 1, 2); easeFastEnd(blurLength, 2, 3);
        }
        adjustment.motionBlur = true;
        return 1;
    }

    function animateCutSide(property, start, end, first, last, arrivesAtCut) {
        if (!property) { return false; }
        clearKeys(property);
        property.setValueAtTime(start, first);
        property.setValueAtTime(end, last);
        if (arrivesAtCut) { easeFastEnd(property, 1, 2); }
        else { easeFastStart(property, 1, 2); }
        return true;
    }

    function pairedCutTimes(comp, layers, options) {
        if (layers.length < 1 || layers.length > 2) { throw new Error("Select one scene at the playhead or two adjacent scene layers for this cut transition."); }
        layers.sort(function (a, b) { return a.inPoint - b.inPoint; });
        var outgoing = layers[0], incoming = layers.length === 2 ? layers[1] : layers[0], fd = comp.frameDuration;
        if (isProtected(outgoing) || isProtected(incoming)) { throw new Error("The selected transition layers cannot be protected or locked."); }
        var cut = layers.length === 2 ? incoming.inPoint : Math.max(outgoing.inPoint + fd * 2, Math.min(comp.time, outgoing.outPoint - fd * 2));
        var frames = Math.max(3, Math.min(9, Number(options.duration) || 5)), span = frames * fd;
        var outStart = Math.max(outgoing.inPoint, cut - span), outEnd = Math.min(outgoing.outPoint - fd * 0.25, cut);
        var inStart = Math.max(incoming.inPoint, cut), inEnd = Math.min(incoming.outPoint - fd, cut + span);
        if (outEnd <= outStart || inEnd <= inStart) { throw new Error("The two selected layers need more usable frames around their cut."); }
        return {outgoing:outgoing,incoming:incoming,cut:cut,outStart:outStart,outEnd:outEnd,inStart:inStart,inEnd:inEnd};
    }

    function addCutBlur(comp, layer, name, start, end, first, last, direction, arrivesAtCut) {
        var effects = layer.property("ADBE Effect Parade");
        var blur = addEffectSafe(effects, "ADBE Motion Blur", name);
        if (!blur) { return false; }
        setProperty(blur, ["ADBE Motion Blur-0001", "Direction"], direction);
        return animateCutSide(propertyByNamesOrIndex(blur, ["ADBE Motion Blur-0002", "Blur Length"], 2), start, end, first, last, arrivesAtCut);
    }

    function addCutExposure(layer, name, start, end, first, last, arrivesAtCut) {
        var effect = addEffectSafe(layer.property("ADBE Effect Parade"), "ADBE Exposure2", name);
        if (!effect) { return false; }
        return animateCutSide(propertyByNamesOrIndex(effect, ["ADBE Exposure2-0003", "Exposure"], 3), start, end, first, last, arrivesAtCut);
    }

    function applyPairedTransition(comp, layers, options) {
        var timing = pairedCutTimes(comp, layers, options), amount = Math.max(80, Number(options.amount) || 150);
        var adjustment = createEffectAdjustment(comp, options.name, timing.outStart, timing.inEnd, timing.outgoing);
        var effects = adjustment.property("ADBE Effect Parade");
        var start = timing.outStart, cut = timing.cut, end = timing.inEnd;
        if (options.transition === "flashSmear") {
            var flash = addEffectSafe(effects, "ADBE Exposure2", "TonyFX - Flash Smear Exposure");
            animateThree(propertyByNamesOrIndex(flash, ["ADBE Exposure2-0003", "Exposure"], 3), start, cut, end, 0, 1.55, 0);
            var smear = addEffectSafe(effects, "ADBE Motion Blur", "TonyFX - Flash Smear Blur");
            setProperty(smear, ["ADBE Motion Blur-0001", "Direction"], 38);
            animateThree(propertyByNamesOrIndex(smear, ["ADBE Motion Blur-0002", "Blur Length"], 2), start, cut, end, 4, amount, 4);
        } else if (options.transition === "zoomBlur") {
            var zoomTransform = addTransformEffect(effects, "TonyFX - Zoom Blur Transform", comp);
            animateThree(propertyByNamesOrIndex(zoomTransform, ["Scale", "Scale Height"], 4), start, cut, end, 100, 128, 100);
            var radial = addEffectSafe(effects, "ADBE Radial Blur", "TonyFX - Zoom Radial Blur");
            setProperty(radial, ["Type", "ADBE Radial Blur-0003"], 2);
            animateThree(propertyByNamesOrIndex(radial, ["Amount", "ADBE Radial Blur-0001"], 1), start, cut, end, 2, amount * 0.44, 2);
        } else if (options.transition === "blackDip") {
            var dip = addEffectSafe(effects, "ADBE Exposure2", "TonyFX - Black Dip Exposure");
            animateThree(propertyByNamesOrIndex(dip, ["ADBE Exposure2-0003", "Exposure"], 3), start, cut, end, 0, -2.7, 0);
        } else if (options.transition === "rgbWhip") {
            var rgbTransform = addTransformEffect(effects, "TonyFX - RGB Whip Transform", comp);
            var rgbPosition = propertyByNamesOrIndex(rgbTransform, ["Position"], 2), center = [comp.width / 2, comp.height / 2], distance = comp.width * 0.52;
            clearKeys(rgbPosition); rgbPosition.setValueAtTime(start, center); rgbPosition.setValueAtTime(cut, [center[0] - distance, center[1]]); rgbPosition.setValueAtTime(cut + comp.frameDuration * 0.25, [center[0] + distance, center[1]]); rgbPosition.setValueAtTime(end, center);
            easeFastStart(rgbPosition, 1, 2); easeFastEnd(rgbPosition, 3, 4);
            var rgb = addEffectSafe(effects, "ADBE Channel Blur", "TonyFX - RGB Whip Split");
            animateThree(propertyByNames(rgb, ["ADBE Channel Blur-0001", "Red Blurriness"]), start, cut, end, 2, 18, 2);
            animateThree(propertyByNames(rgb, ["ADBE Channel Blur-0003", "Blue Blurriness"]), start, cut, end, 2, 14, 2);
            var rgbBlur = addEffectSafe(effects, "ADBE Motion Blur", "TonyFX - RGB Whip Blur");
            setProperty(rgbBlur, ["ADBE Motion Blur-0001", "Direction"], 0);
            animateThree(propertyByNamesOrIndex(rgbBlur, ["ADBE Motion Blur-0002", "Blur Length"], 2), start, cut, end, 4, amount, 4);
        } else { throw new Error("Unknown TonyFX cut transition."); }
        adjustment.motionBlur = true;
        return 1;
    }

    function applyEffectPreset(comp, layer, options) {
        var effects = layer.property("ADBE Effect Parade");
        var d = frameTime(comp, Math.min(10, options.duration || 5));
        var t = Math.max(layer.inPoint, Math.min(comp.time, layer.outPoint - comp.frameDuration * 2));
        var end = Math.min(layer.outPoint, t + d);
        if (end <= t + comp.frameDuration * 0.5) { t = layer.inPoint; end = Math.min(layer.outPoint, t + d); }
        var effect, mid = t + (end - t) * 0.5;
        if (options.effect === "glow") {
            removeNamedProperty(effects, "TUF - Glow Pulse");
            effect = addEffectSafe(effects, "ADBE Glo2", "TonyFX - Glow Pulse");
            if (!effect) { return false; }
            setProperty(effect, ["ADBE Glo2-0002", "Glow Threshold"], 55);
            setProperty(effect, ["ADBE Glo2-0003", "Glow Radius"], 72);
            var intensity = propertyByNames(effect, ["ADBE Glo2-0004", "Glow Intensity"]);
            if (intensity) { animateImpact(intensity, t, end, 1.65, 0.12); }
        } else if (options.effect === "directionalBlur") {
            removeNamedProperty(effects, "TUF - Directional Smear");
            effect = addEffectSafe(effects, "ADBE Motion Blur", "TonyFX - Directional Smear");
            if (!effect) { return false; }
            setProperty(effect, ["ADBE Motion Blur-0001", "Direction"], 38);
            var length = propertyByNames(effect, ["ADBE Motion Blur-0002", "Blur Length"]);
            if (length) { animateImpact(length, t, end, Math.max(95, Number(options.amount)), 0); }
        } else if (options.effect === "exposure") {
            removeNamedProperty(effects, "TUF - Exposure Flash");
            effect = addEffectSafe(effects, "ADBE Exposure2", "TonyFX - Exposure Flash");
            if (!effect) { return false; }
            var exposure = propertyByNamesOrIndex(effect, ["ADBE Exposure2-0003", "Exposure"], 3);
            if (exposure) { animateImpact(exposure, t, end, Math.max(1.3, Number(options.amount) / 100), 0); }
        } else if (options.effect === "chromatic") {
            effect = addEffectSafe(effects, "ADBE Channel Blur", "TUF - Chromatic Hit");
            if (!effect) { return false; }
            animateImpact(propertyByNames(effect, ["ADBE Channel Blur-0001", "Red Blurriness"]), t, end, Math.max(14, Number(options.amount) * 0.12), 0);
            animateImpact(propertyByNames(effect, ["ADBE Channel Blur-0003", "Blue Blurriness"]), t, end, Math.max(11, Number(options.amount) * 0.09), 0);
        } else if (options.effect === "vhs") {
            effect = addEffectSafe(effects, "ADBE Noise", "TUF - Clean VHS Noise");
            if (!effect) { return false; }
            setProperty(effect, ["ADBE Noise-0001", "Amount of Noise"], 7);
            addEffectSafe(effects, "ADBE Posterize Time", "TUF - VHS Cadence");
        } else if (options.effect === "duotone") {
            effect = addEffectSafe(effects, "ADBE Tint", "TUF - Duotone");
            if (!effect) { return false; }
            setProperty(effect, ["ADBE Tint-0003", "Amount to Tint"], 62);
        } else if (options.effect === "ghostZoom") {
            effect = addTransformEffect(effects, "TonyFX - Ghost Zoom", comp);
            if (!effect) { return false; }
            var ghostScale = propertyByNamesOrIndex(effect, ["Scale", "Scale Height"], 4);
            animateImpact(ghostScale, t, end, Math.max(124, Number(options.amount) * 0.94), 100);
            var ghostEcho = addEffectSafe(effects, "ADBE Echo", "TonyFX - Ghost Echo");
            if (ghostEcho) {
                setProperty(ghostEcho, ["Echo Time (seconds)", "ADBE Echo-0001"], -comp.frameDuration);
                setProperty(ghostEcho, ["Number Of Echoes", "Number of Echoes", "ADBE Echo-0002"], 3);
                setProperty(ghostEcho, ["Starting Intensity", "ADBE Echo-0003"], 0.58);
                setProperty(ghostEcho, ["Decay", "ADBE Echo-0004"], 0.62);
            }
        } else if (options.effect === "echoTrail") {
            effect = addEffectSafe(effects, "ADBE Echo", "TonyFX - Echo Trails");
            if (!effect) { return false; }
            setProperty(effect, ["Echo Time (seconds)", "ADBE Echo-0001"], -comp.frameDuration);
            setProperty(effect, ["Number Of Echoes", "Number of Echoes", "ADBE Echo-0002"], 5);
            setProperty(effect, ["Starting Intensity", "ADBE Echo-0003"], 0.62);
            setProperty(effect, ["Decay", "ADBE Echo-0004"], 0.68);
        } else if (options.effect === "radialZoom") {
            effect = addEffectSafe(effects, "ADBE Radial Blur", "TonyFX - Radial Zoom Blur");
            if (!effect) { return false; }
            var radialAmount = propertyByNamesOrIndex(effect, ["Amount", "ADBE Radial Blur-0001"], 1);
            setProperty(effect, ["Center", "ADBE Radial Blur-0002"], [comp.width / 2, comp.height / 2]);
            setProperty(effect, ["Type", "ADBE Radial Blur-0003"], 2);
            animateImpact(radialAmount, t, end, Math.max(42, Number(options.amount) * 0.42), 0);
        } else if (options.effect === "opticalRipple") {
            effect = addEffectSafe(effects, "ADBE Magnify", "TonyFX - Optical Ripple");
            if (!effect) { return false; }
            var rippleCenter = [comp.width / 2, comp.height / 2];
            setProperty(effect, ["ADBE Magnify-0001", "Center"], rippleCenter);
            setProperty(effect, ["ADBE Magnify-0003", "Magnification"], 108);
            setProperty(effect, ["ADBE Magnify-0004", "Feather"], 78);
            var rippleSize = propertyByNamesOrIndex(effect, ["ADBE Magnify-0002", "Size"], 4);
            var rippleOpacity = propertyByNamesOrIndex(effect, ["ADBE Magnify-0005", "Opacity"], 6);
            animateImpact(rippleSize, t, end, Math.min(comp.width, comp.height) * 0.18, Math.min(comp.width, comp.height) * 0.72);
            animateImpact(rippleOpacity, t, end, 72, 0);
            var bulge = addEffectSafe(effects, "ADBE Bulge", "TonyFX - Ripple Refraction");
            if (bulge) {
                setProperty(bulge, ["ADBE Bulge-0003", "Bulge Center"], rippleCenter);
                setProperty(bulge, ["ADBE Bulge-0001", "Horizontal Radius"], Math.min(comp.width, comp.height) * 0.3);
                setProperty(bulge, ["ADBE Bulge-0002", "Vertical Radius"], Math.min(comp.width, comp.height) * 0.3);
                animateImpact(propertyByNamesOrIndex(bulge, ["ADBE Bulge-0004", "Bulge Height"], 4), t, end, 0.28, 0);
            }
        } else if (options.effect === "halation") {
            effect = addEffectSafe(effects, "ADBE Glo2", "TonyFX - Soft Halation");
            if (!effect) { return false; }
            setProperty(effect, ["ADBE Glo2-0002", "Glow Threshold"], 68);
            setProperty(effect, ["ADBE Glo2-0003", "Glow Radius"], 42);
            setProperty(effect, ["ADBE Glo2-0004", "Glow Intensity"], 0.48);
            var softGlow = addEffectSafe(effects, "ADBE Glo2", "TonyFX - Halation Bloom");
            if (softGlow) {
                setProperty(softGlow, ["ADBE Glo2-0002", "Glow Threshold"], 82);
                setProperty(softGlow, ["ADBE Glo2-0003", "Glow Radius"], 96);
                setProperty(softGlow, ["ADBE Glo2-0004", "Glow Intensity"], 0.22);
            }
        } else if (options.effect === "flashShake") {
            effect = addEffectSafe(effects, "ADBE Exposure2", "TonyFX - Flash Impact");
            if (!effect) { return false; }
            animateImpact(propertyByNamesOrIndex(effect, ["ADBE Exposure2-0003", "Exposure"], 3), t, end, 1.95, 0);
            var shakeTransform = addTransformEffect(effects, "TonyFX - Impact Shake", comp);
            if (shakeTransform) { animateEffectShake(shakeTransform, comp, t, 4, Number(options.amount) || 120); }
        } else if (options.effect === "blackHit") {
            effect = addEffectSafe(effects, "ADBE Exposure2", "TonyFX - Clean Black Hit");
            if (!effect) { return false; }
            animateImpact(propertyByNamesOrIndex(effect, ["ADBE Exposure2-0003", "Exposure"], 3), t, end, -3.8, 0);
        } else if (options.effect === "lensGlimmer") {
            effect = addEffectSafe(effects, "ADBE Lens Flare", "TonyFX - Lens Glimmer");
            if (!effect) { return false; }
            setProperty(effect, ["ADBE Lens Flare-0001", "Flare Center"], [comp.width * 0.62, comp.height * 0.38]);
            animateImpact(propertyByNamesOrIndex(effect, ["ADBE Lens Flare-0002", "Flare Brightness"], 2), t, end, Math.max(90, Number(options.amount)), 0);
            setProperty(effect, ["ADBE Lens Flare-0003", "Blend With Original"], 55);
        } else if (options.effect === "punchFlicker") {
            effect = addEffectSafe(effects, "ADBE Exposure2", "TonyFX - Punch Flicker");
            if (!effect) { return false; }
            var flicker = propertyByNamesOrIndex(effect, ["ADBE Exposure2-0003", "Exposure"], 3), flickerFrame = comp.frameDuration;
            clearKeys(flicker);
            flicker.setValueAtTime(t, 0); flicker.setValueAtTime(t + flickerFrame, 1.15); flicker.setValueAtTime(t + flickerFrame * 2, -0.28); flicker.setValueAtTime(t + flickerFrame * 3, 0.46); flicker.setValueAtTime(t + flickerFrame * 4, 0);
            for (var pf = 1; pf <= flicker.numKeys; pf++) { temporalEase(flicker, pf, 78, 78); }
        } else if (options.effect === "rgbPulse") {
            effect = addEffectSafe(effects, "ADBE Channel Blur", "TonyFX - RGB Pulse");
            if (!effect) { return false; }
            animateImpact(propertyByNames(effect, ["ADBE Channel Blur-0001", "Red Blurriness"]), t, end, Math.max(16, Number(options.amount) * 0.12), 0);
            animateImpact(propertyByNames(effect, ["ADBE Channel Blur-0003", "Blue Blurriness"]), t, end, Math.max(12, Number(options.amount) * 0.09), 0);
        } else if (options.effect === "cameraSnap") {
            effect = addTransformEffect(effects, "TonyFX - Camera Snap", comp);
            if (!effect) { return false; }
            var snapHeight = propertyByNames(effect, ["Scale", "Scale Height"]), snapWidth = propertyByNames(effect, ["Scale Width"]), snapRotation = propertyByNames(effect, ["Rotation"]);
            if (snapHeight) { clearKeys(snapHeight); snapHeight.setValueAtTime(t, 0); snapHeight.setValueAtTime(t + d * 0.62, 185); snapHeight.setValueAtTime(t + d, 100); easyEaseAll(snapHeight); }
            if (snapWidth && snapWidth !== snapHeight) { clearKeys(snapWidth); snapWidth.setValueAtTime(t, 0); snapWidth.setValueAtTime(t + d * 0.62, 185); snapWidth.setValueAtTime(t + d, 100); easyEaseAll(snapWidth); }
            if (snapRotation) { clearKeys(snapRotation); snapRotation.setValueAtTime(t, -16); snapRotation.setValueAtTime(t + d * 0.62, 5); snapRotation.setValueAtTime(t + d, 0); easyEaseAll(snapRotation); }
        } else if (options.effect === "zoomStutter") {
            effect = addTransformEffect(effects, "TonyFX - Zoom Stutter", comp);
            if (!effect) { return false; }
            var stutterHeight = propertyByNames(effect, ["Scale", "Scale Height"]), stutterWidth = propertyByNames(effect, ["Scale Width"]), zf = comp.frameDuration;
            var stutterValues = [100, 145, 90, 135, 100], stutterStep = Math.max(1, Math.round((Number(options.duration) || 16) / 4));
            var stutterProperties = [stutterHeight, stutterWidth];
            for (var sp = 0; sp < stutterProperties.length; sp++) {
                var stutterProperty = stutterProperties[sp];
                if (!stutterProperty || (sp === 1 && stutterProperty === stutterHeight)) { continue; }
                clearKeys(stutterProperty);
                for (var sv = 0; sv < stutterValues.length; sv++) { stutterProperty.setValueAtTime(t + zf * stutterStep * sv, stutterValues[sv]); }
                easyEaseAll(stutterProperty);
            }
        } else if (options.effect === "whipLeft" || options.effect === "whipRight") {
            effect = addTransformEffect(effects, "TonyFX - Fast Whip", comp);
            if (!effect) { return false; }
            var whipPosition = propertyByNamesOrIndex(effect, ["Position"], 2), sign = options.effect === "whipLeft" ? -1 : 1;
            clearKeys(whipPosition);
            whipPosition.setValueAtTime(t, [comp.width / 2, comp.height / 2]);
            whipPosition.setValueAtTime(t + d, [comp.width / 2 + sign * Math.max(comp.width * 0.48, Number(options.amount) * 3), comp.height / 2]);
            temporalEase(whipPosition, 1, 16, 88); temporalEase(whipPosition, 2, 88, 16);
            var whipBlur = addEffectSafe(effects, "ADBE Motion Blur", "TonyFX - Whip Directional Blur");
            if (whipBlur) {
                setProperty(whipBlur, ["ADBE Motion Blur-0001", "Direction"], 0);
                animateImpact(propertyByNames(whipBlur, ["ADBE Motion Blur-0002", "Blur Length"]), t, end, Math.max(55, Number(options.amount) * 0.72), 0);
            }
        }
        return !!effect;
    }

    function applyImpactShake(comp, layer, options) {
        var effects = layer.property("ADBE Effect Parade"), name = "TonyFX - Impact Shake";
        removeNamedProperty(effects, name);
        var transform = addTransformEffect(effects, name, comp);
        if (!transform) { return false; }
        var position = propertyByNamesOrIndex(transform, ["Position"], 2);
        var base = [comp.width / 2, comp.height / 2], amount = Math.max(90, Number(options.amount) * 0.35), t = Math.max(layer.inPoint, comp.time), fd = comp.frameDuration;
        clearKeys(position);
        position.setValueAtTime(t, base);
        position.setValueAtTime(t + fd, addValues(base, [amount, -amount * 0.55]));
        position.setValueAtTime(t + fd * 2, addValues(base, [-amount * 0.62, amount * 0.34]));
        position.setValueAtTime(t + fd * 3, addValues(base, [amount * 0.22, -amount * 0.12]));
        position.setValueAtTime(t + fd * 4, base);
        easyEaseAll(position);
        layer.motionBlur = true;
        return true;
    }

    function normalizedColor(value, fallback) {
        if (!(value instanceof Array) || value.length < 3) { return fallback || [1, 1, 1]; }
        var divisor = (Number(value[0]) > 1 || Number(value[1]) > 1 || Number(value[2]) > 1) ? 255 : 1;
        return [Math.max(0, Math.min(1, Number(value[0]) / divisor)), Math.max(0, Math.min(1, Number(value[1]) / divisor)), Math.max(0, Math.min(1, Number(value[2]) / divisor))];
    }

    function applyTextStyleToLayer(layer, options) {
        var text = layer.property("ADBE Text Properties");
        if (!text || isProtected(layer)) { return false; }
        var sourceText = text.property("ADBE Text Document"), documentValue = sourceText.value;
        try { if (options.font) { documentValue.font = String(options.font); } } catch (ignoreFont) {}
        if (options.fontSize) { documentValue.fontSize = Math.max(8, Number(options.fontSize)); }
        documentValue.applyFill = true;
        documentValue.fillColor = normalizedColor(options.fill, [1, 1, 1]);
        documentValue.applyStroke = !!options.strokeEnabled;
        documentValue.strokeColor = normalizedColor(options.stroke, [0.05, 0.05, 0.05]);
        documentValue.strokeWidth = Math.max(0, Number(options.strokeWidth) || 0);
        try { documentValue.strokeOverFill = false; } catch (ignoreStrokeOrder) {}
        sourceText.setValue(documentValue);
        var effects = layer.property("ADBE Effect Parade");
        removeNamedProperty(effects, "TonyFX - Text Shadow");
        removeNamedProperty(effects, "TonyFX - Text Glow");
        if (options.shadowEnabled) {
            var shadow = addEffectSafe(effects, "ADBE Drop Shadow", "TonyFX - Text Shadow");
            if (shadow) {
                setProperty(shadow, ["ADBE Drop Shadow-0001", "Shadow Color"], normalizedColor(options.shadowColor, [0, 0, 0]));
                setProperty(shadow, ["ADBE Drop Shadow-0002", "Opacity"], Math.max(0, Math.min(100, Number(options.shadowOpacity) || 0)));
                setProperty(shadow, ["ADBE Drop Shadow-0003", "Direction"], Number(options.shadowDirection) || 135);
                setProperty(shadow, ["ADBE Drop Shadow-0004", "Distance"], Math.max(0, Number(options.shadowDistance) || 0));
                setProperty(shadow, ["ADBE Drop Shadow-0005", "Softness"], Math.max(0, Number(options.shadowSoftness) || 0));
            }
        }
        if (options.glowEnabled) {
            var glow = addEffectSafe(effects, "ADBE Glo2", "TonyFX - Text Glow");
            if (glow) {
                setProperty(glow, ["ADBE Glo2-0002", "Glow Threshold"], 42);
                setProperty(glow, ["ADBE Glo2-0003", "Glow Radius"], Math.max(1, Number(options.glowRadius) || 45));
                setProperty(glow, ["ADBE Glo2-0004", "Glow Intensity"], Math.max(0, Number(options.glowIntensity) || 1));
            }
        }
        return true;
    }

    api.applyTextStyle = function (json) {
        try {
            var options = parseJSON(json), comp = activeComp(), layers = selectedLayers(comp), changed = 0;
            if (!layers.length) { throw new Error("Select one or more text layers first."); }
            app.beginUndoGroup("TonyFX Text Style");
            for (var i = 0; i < layers.length; i++) { if (applyTextStyleToLayer(layers[i], options)) { changed++; } }
            app.endUndoGroup();
            if (!changed) { throw new Error("No editable text layers were selected."); }
            return response({ok:true,message:"Styled " + changed + " selected text layer(s)."});
        } catch (error) { try { app.endUndoGroup(); } catch (ignore) {} return response({ok:false,error:error.toString()}); }
    };

    function removeTonyFxTextTreatment(layer) {
        var effects = layer.property("ADBE Effect Parade"), text = layer.property("ADBE Text Properties");
        if (effects) {
            for (var e = effects.numProperties; e >= 1; e--) { if (String(effects.property(e).name).indexOf("TonyFX - Text FX") === 0) { effects.property(e).remove(); } }
        }
        if (text) {
            var animators = text.property("ADBE Text Animators");
            for (var a = animators.numProperties; a >= 1; a--) { if (String(animators.property(a).name).indexOf("TonyFX - Text FX") === 0) { animators.property(a).remove(); } }
        }
    }

    function addTextFxShadow(effects, name, opacity, direction, distance, softness, color) {
        var shadow = addEffectSafe(effects, "ADBE Drop Shadow", name);
        if (!shadow) { return null; }
        setProperty(shadow, ["ADBE Drop Shadow-0001", "Shadow Color"], color || [0, 0, 0]);
        setProperty(shadow, ["ADBE Drop Shadow-0002", "Opacity"], opacity);
        setProperty(shadow, ["ADBE Drop Shadow-0003", "Direction"], direction);
        setProperty(shadow, ["ADBE Drop Shadow-0004", "Distance"], distance);
        setProperty(shadow, ["ADBE Drop Shadow-0005", "Softness"], softness);
        return shadow;
    }

    function addTextFxGlow(effects, name, radius, intensity, threshold) {
        var glow = addEffectSafe(effects, "ADBE Glo2", name);
        if (!glow) { return null; }
        setProperty(glow, ["ADBE Glo2-0002", "Glow Threshold"], threshold);
        setProperty(glow, ["ADBE Glo2-0003", "Glow Radius"], radius);
        setProperty(glow, ["ADBE Glo2-0004", "Glow Intensity"], intensity);
        return glow;
    }

    function addTextFxProperty(group, matchName, value) {
        try { var property = group.addProperty(matchName); property.setValue(value); return property; } catch (ignore) { return null; }
    }

    function addTextFxAnimator(layer, name, start, end, unit, smoothness, values) {
        var text = layer.property("ADBE Text Properties"), animators = text.property("ADBE Text Animators");
        var animator = animators.addProperty("ADBE Text Animator"); animator.name = "TonyFX - Text FX - " + name;
        var props = animator.property("ADBE Text Animator Properties");
        if (values.opacity !== undefined) { addTextFxProperty(props, "ADBE Text Opacity", values.opacity); }
        if (values.position) { addTextFxProperty(props, "ADBE Text Position 3D", values.position); }
        if (values.scale) { addTextFxProperty(props, "ADBE Text Scale 3D", values.scale); }
        if (values.rotationX !== undefined) { addTextFxProperty(props, "ADBE Text Rotation X", values.rotationX); }
        if (values.rotationY !== undefined) { addTextFxProperty(props, "ADBE Text Rotation Y", values.rotationY); }
        if (values.rotationZ !== undefined) { addTextFxProperty(props, "ADBE Text Rotation", values.rotationZ); }
        if (values.blur !== undefined) { addTextFxProperty(props, "ADBE Text Blur", [values.blur, values.blur]); }
        if (values.tracking !== undefined) { addTextFxProperty(props, "ADBE Text Tracking Amount", values.tracking); }
        var selector = animator.property("ADBE Text Selectors").addProperty("ADBE Text Selector"), advanced = selector.property("ADBE Text Range Advanced");
        try { advanced.property("ADBE Text Range Type2").setValue(unit === "words" ? 3 : 2); } catch (ignoreUnit) {}
        try { advanced.property("ADBE Text Selector Smoothness").setValue(smoothness); } catch (ignoreSmooth) {}
        var startProp = selector.property("ADBE Text Percent Start") || selector.property("Start");
        startProp.setValueAtTime(start, 0); startProp.setValueAtTime(end, 100); easyEaseAll(startProp);
        return animator;
    }

    function applyTextEffectToLayer(comp, layer, options, forcedStart, forcedEnd) {
        if (!layer.property("ADBE Text Properties") || isProtected(layer)) { return false; }
        removeTonyFxTextTreatment(layer);
        var id = String(options.id || "cleanReveal"), strength = Math.max(0.1, Math.min(2, (Number(options.strength) || 100) / 100));
        var duration = Math.max(4, Math.min(90, Number(options.duration) || 18)), start = forcedStart;
        if (start === undefined || start === null) { start = comp.time >= layer.inPoint && comp.time < layer.outPoint ? comp.time : layer.inPoint; }
        var end = forcedEnd;
        if (end === undefined || end === null) { end = start + duration * comp.frameDuration; }
        end = Math.min(layer.outPoint, Math.max(start + comp.frameDuration * 2, end));
        var effects = layer.property("ADBE Effect Parade"), glow, intensity;
        if (id === "none") { return true; }
        if (id === "deepShadow") {
            addTextFxShadow(effects, "TonyFX - Text FX - Deep Shadow Near", Math.min(100, 78 * strength), 135, 8 * strength, 8, [0.03, 0.03, 0.04]);
            addTextFxShadow(effects, "TonyFX - Text FX - Deep Shadow Far", Math.min(100, 58 * strength), 135, 22 * strength, 22, [0, 0, 0]);
            return true;
        }
        if (id === "longShadow") {
            addTextFxShadow(effects, "TonyFX - Text FX - Long Shadow 1", Math.min(100, 82 * strength), 135, 7 * strength, 1, [0.09, 0.1, 0.12]);
            addTextFxShadow(effects, "TonyFX - Text FX - Long Shadow 2", Math.min(100, 72 * strength), 135, 15 * strength, 2, [0.04, 0.05, 0.06]);
            addTextFxShadow(effects, "TonyFX - Text FX - Long Shadow 3", Math.min(100, 58 * strength), 135, 28 * strength, 13, [0, 0, 0]);
            return true;
        }
        if (id === "dualGlow") {
            addTextFxGlow(effects, "TonyFX - Text FX - Dual Glow Core", 18 * strength, 1.35 * strength, 36);
            addTextFxGlow(effects, "TonyFX - Text FX - Dual Glow Bloom", 62 * strength, 0.8 * strength, 48);
            return true;
        }
        if (id === "neonTube") {
            addTextFxGlow(effects, "TonyFX - Text FX - Neon Core", 7 * strength, 2.2 * strength, 18);
            addTextFxGlow(effects, "TonyFX - Text FX - Neon Bloom", 52 * strength, 1.2 * strength, 42);
            addTextFxShadow(effects, "TonyFX - Text FX - Neon Depth", Math.min(100, 52 * strength), 135, 8 * strength, 18, [0, 0.12, 0.14]);
            return true;
        }
        if (id === "bevelEdge") {
            addTextFxShadow(effects, "TonyFX - Text FX - Bevel Dark", Math.min(100, 76 * strength), 135, 5 * strength, 1, [0.08, 0.06, 0.03]);
            addTextFxShadow(effects, "TonyFX - Text FX - Bevel Light", Math.min(100, 52 * strength), 315, 3 * strength, 1, [1, 0.95, 0.78]);
            addTextFxGlow(effects, "TonyFX - Text FX - Bevel Finish", 9 * strength, 0.35 * strength, 58);
            return true;
        }
        if (id === "softBloom") {
            addTextFxGlow(effects, "TonyFX - Text FX - Soft Bloom Core", 12 * strength, 0.72 * strength, 54);
            addTextFxGlow(effects, "TonyFX - Text FX - Soft Bloom Outer", 88 * strength, 0.46 * strength, 68);
            return true;
        }
        if (id === "chromaticShadow") {
            addTextFxShadow(effects, "TonyFX - Text FX - Chromatic Cyan", Math.min(100, 74 * strength), 180, 6 * strength, 5, [0,0.78,1]);
            addTextFxShadow(effects, "TonyFX - Text FX - Chromatic Red", Math.min(100, 74 * strength), 0, 6 * strength, 5, [1,0.08,0.24]);
            addTextFxShadow(effects, "TonyFX - Text FX - Chromatic Depth", Math.min(100, 48 * strength), 135, 12 * strength, 16, [0,0,0]);
            return true;
        }
        if (id === "echoTrail") {
            addTextFxShadow(effects, "TonyFX - Text FX - Echo 1", Math.min(100, 62 * strength), 180, 7 * strength, 2, [0.18,0.2,0.24]);
            addTextFxShadow(effects, "TonyFX - Text FX - Echo 2", Math.min(100, 44 * strength), 180, 15 * strength, 4, [0.10,0.12,0.15]);
            addTextFxShadow(effects, "TonyFX - Text FX - Echo 3", Math.min(100, 28 * strength), 180, 27 * strength, 8, [0.04,0.05,0.07]);
            return true;
        }
        if (id === "sweep") {
            glow = addTextFxGlow(effects, "TonyFX - Text FX - Highlight Sweep", 38 * strength, 0.15, 46);
            if (glow) {
                intensity = propertyByNames(glow, ["ADBE Glo2-0004", "Glow Intensity"]);
                if (intensity) { clearKeys(intensity); intensity.setValueAtTime(start, 0.15); intensity.setValueAtTime(start + (end - start) * 0.55, 2.4 * strength); intensity.setValueAtTime(end, 0.35); easyEaseAll(intensity); }
            }
            addTextFxAnimator(layer, "Highlight Sweep", start, end, "words", 16, {opacity:0,blur:10 * strength});
            return true;
        }
        try { layer.threeDPerChar = id === "flipX" || id === "flipY" || id === "depthPush" || id === "cascade3d" || id === "impact3d"; } catch (ignore3D) {}
        if (id === "flipX") { addTextFxAnimator(layer, "3D Flip X", start, end, "characters", 14, {opacity:0,rotationX:88 * strength,position:[0,18 * strength,-120 * strength]}); return true; }
        if (id === "flipY") { addTextFxAnimator(layer, "3D Flip Y", start, end, "characters", 14, {opacity:0,rotationY:-88 * strength,position:[-18 * strength,0,-120 * strength]}); return true; }
        if (id === "depthPush") { addTextFxAnimator(layer, "3D Depth Push", start, end, "characters", 20, {opacity:0,position:[0,0,-340 * strength],scale:[55,55,100],blur:8 * strength}); return true; }
        if (id === "cascade3d") { addTextFxAnimator(layer, "3D Cascade", start, end, "characters", 8, {opacity:0,position:[-26 * strength,30 * strength,-220 * strength],rotationX:66 * strength,rotationY:-34 * strength}); return true; }
        if (id === "blurTrack") { addTextFxAnimator(layer, "Blur Tracking", start, end, "characters", 18, {opacity:0,tracking:34 * strength,blur:14 * strength}); return true; }
        if (id === "impact3d") {
            addTextFxAnimator(layer, "3D Impact", start, end, "characters", 12, {opacity:0,position:[0,0,180 * strength],rotationX:-42 * strength,blur:7 * strength});
            var scale = layer.property("ADBE Transform Group").property("ADBE Scale"), middle = start + (end - start) * 0.68;
            clearKeys(scale); scale.setValueAtTime(start, [185 * strength,185 * strength]); scale.setValueAtTime(middle, [92,92]); scale.setValueAtTime(end, [100,100]); easyEaseAll(scale);
            return true;
        }
        if (id === "focusSnap") { addTextFxAnimator(layer, "Focus Snap", start, end, "characters", 10, {opacity:0,scale:[142,142,100],blur:22 * strength,tracking:20 * strength}); return true; }
        if (id === "kineticTilt") { addTextFxAnimator(layer, "Kinetic Tilt", start, end, "characters", 10, {opacity:0,position:[-46 * strength,24 * strength,0],rotationZ:-18 * strength,scale:[118,118,100]}); return true; }
        addTextFxAnimator(layer, "Clean Reveal", start, end, "words", 22, {opacity:0});
        return true;
    }

    api.applyTextEffect = function (json) {
        try {
            var options = parseJSON(json), comp = activeComp(), layers = selectedLayers(comp), changed = 0;
            if (!layers.length) { throw new Error("Select one or more text layers first."); }
            app.beginUndoGroup("TonyFX Text Treatment");
            for (var i = 0; i < layers.length; i++) { if (applyTextEffectToLayer(comp, layers[i], options)) { changed++; } }
            app.endUndoGroup();
            if (!changed) { throw new Error("No editable text layers were selected."); }
            return response({ok:true,message:"Applied " + String(options.id || "text treatment") + " to " + changed + " text layer(s)."});
        } catch (error) { try { app.endUndoGroup(); } catch (ignore) {} return response({ok:false,error:error.toString() + (error.line ? " at line " + error.line : "")}); }
    };

    api.createStyledText = function (json) {
        try {
            var options=parseJSON(json), comp=activeComp(), value=String(options.text || "").replace(/^\s+|\s+$/g, "");
            if (!value) { throw new Error("Type the text to create first."); }
            var durationFrames=Math.max(24,Number(options.durationFrames)||120), start=Math.max(0,Math.min(comp.duration-comp.frameDuration,comp.time));
            var end=Math.min(comp.duration,start+durationFrames*comp.frameDuration);
            if (end <= start + comp.frameDuration * 2) { throw new Error("The active composition has no room for the text layer at the current time."); }
            app.beginUndoGroup("TonyFX Create Styled Text");
            var layer=comp.layers.addText(value), sourceText=layer.property("ADBE Text Properties").property("ADBE Text Document"), doc=sourceText.value;
            applyTextStyleToLayer(layer,options.style||{});
            doc=sourceText.value; doc.justification=ParagraphJustification.CENTER_JUSTIFY; sourceText.setValue(doc);
            layer.name="TONYFX TEXT - " + value.substring(0,32); layer.startTime=0; layer.inPoint=start; layer.outPoint=end;
            var placement=String(options.placement||"center"), y=placement==="bottom"?comp.height*0.82:placement==="top"?comp.height*0.18:comp.height*0.5;
            layer.property("ADBE Transform Group").property("ADBE Position").setValue([comp.width/2,y]);
            var motion=options.animation||{id:"text-word-fade",name:"Word Fade",mode:"opacity",unit:"words",duration:20};
            motion.matchedExit=options.matchedExit!==false; motion.exitDuration=Math.max(6,Number(options.exitDuration)||Number(motion.duration)||20);
            applyTextMotion(comp,layer,motion,0);
            if (options.textEffect && String(options.textEffect.id||"none")!=="none") {
                applyTextEffectToLayer(comp,layer,options.textEffect,start,Math.min(end,start+Math.max(4,Number(options.textEffect.duration)||18)*comp.frameDuration));
            }
            layer.label=10; layer.selected=true; app.endUndoGroup();
            return response({ok:true,message:"Created styled text with matched entry and exit animation.",layerName:layer.name});
        } catch(error) { try { app.endUndoGroup(); } catch(ignoreCreateTextUndo) {} return response({ok:false,error:error.toString()+(error.line?" at line "+error.line:"")}); }
    };

    function polygonPoints(count, radius, rotation) {
        var points = [], angleOffset = Number(rotation) || -Math.PI / 2;
        for (var i = 0; i < count; i++) {
            var angle = angleOffset + Math.PI * 2 * i / count;
            points.push([Math.cos(angle) * radius, Math.sin(angle) * radius]);
        }
        return points;
    }

    function starPoints(points, outer, inner) {
        var result = [];
        for (var i = 0; i < points * 2; i++) {
            var radius = i % 2 ? inner : outer, angle = -Math.PI / 2 + Math.PI * i / points;
            result.push([Math.cos(angle) * radius, Math.sin(angle) * radius]);
        }
        return result;
    }

    function iconGeometry(name, size) {
        var h = size / 2, q = size / 4, thin = Math.max(5, size * 0.1);
        if (name === "heart") { return [[[-h * 0.9,-q],[-h * 0.55,-h * 0.72],[0,-h * 0.42],[h * 0.55,-h * 0.72],[h * 0.9,-q],[h * 0.72,q],[0,h],[-h * 0.72,q]]]; }
        if (name === "star") { return [starPoints(5, h, h * 0.43)]; }
        if (name === "sparkle") { return [[ [0,-h],[thin,-thin],[h,0],[thin,thin],[0,h],[-thin,thin],[-h,0],[-thin,-thin] ]]; }
        if (name === "play") { return [[[-h,-h],[h,0],[-h,h]]]; }
        if (name === "pause") { return [[[-h,-h],[-q,-h],[-q,h],[-h,h]],[[q,-h],[h,-h],[h,h],[q,h]]]; }
        if (name === "diamond") { return [[ [0,-h],[h,0],[0,h],[-h,0] ]]; }
        if (name === "bolt") { return [[[q * 0.3,-h],[-h * 0.66,q * 0.15],[-q * 0.05,q * 0.15],[-q * 0.35,h],[h * 0.68,-q * 0.2],[q * 0.05,-q * 0.2]]]; }
        if (name === "check") { return [[[-h * 0.9,0],[-h * 0.55,-q],[-h * 0.05,q],[h * 0.82,-h * 0.72],[h,-h * 0.46],[-h * 0.06,h]]]; }
        if (name === "x") { return [[[-h,-h],[-q,-h],[0,-q],[q,-h],[h,-h],[q,0],[h,h],[q,h],[0,q],[-q,h],[-h,h],[-q,0]]]; }
        if (name === "plus") { return [[[-thin,-h],[thin,-h],[thin,-thin],[h,-thin],[h,thin],[thin,thin],[thin,h],[-thin,h],[-thin,thin],[-h,thin],[-h,-thin],[-thin,-thin]]]; }
        if (name === "arrow-left") { return [[[-h,0],[0,-h],[0,-q],[h,-q],[h,q],[0,q],[0,h]]]; }
        if (name === "arrow-right") { return [[[h,0],[0,-h],[0,-q],[-h,-q],[-h,q],[0,q],[0,h]]]; }
        if (name === "chevron") { return [[[-h,-q],[0,h * 0.7],[h,-q],[h * 0.72,-h * 0.52],[0,q * 0.15],[-h * 0.72,-h * 0.52]]]; }
        if (name === "camera") { return [[[-h,-q],[ -q,-q],[-q * 0.55,-h * 0.58],[q * 0.55,-h * 0.58],[q,-q],[h,-q],[h,h * 0.72],[-h,h * 0.72]],polygonPoints(18,q * 0.82)]; }
        if (name === "music") { return [[[q * 0.1,-h],[h,-h],[h,-h * 0.66],[q * 0.1,-h * 0.66],[q * 0.1,h * 0.46],[-q * 0.7,h * 0.46],[-q * 0.7,h],[q * 0.1,h]]]; }
        if (name === "circle") { return [polygonPoints(36,h)]; }
        if (name === "square") { return [[[-h,-h],[h,-h],[h,h],[-h,h]]]; }
        return [polygonPoints(3,h)];
    }

    function addIconPolygon(root, points, color) {
        var group = root.addProperty("ADBE Vector Group"), vectors = group.property("ADBE Vectors Group");
        var path = vectors.addProperty("ADBE Vector Shape - Group"), shape = new Shape(), zeros = [];
        for (var i = 0; i < points.length; i++) { zeros.push([0, 0]); }
        shape.vertices = points; shape.inTangents = zeros; shape.outTangents = zeros; shape.closed = true; path.property("ADBE Vector Shape").setValue(shape);
        var fill = vectors.addProperty("ADBE Vector Graphic - Fill"); fill.property("ADBE Vector Fill Color").setValue(color);
        return group;
    }

    api.createIcon = function (json) {
        try {
            var options = parseJSON(json), comp = activeComp(), size = Math.max(20, Math.min(800, Number(options.size) || 180));
            var name = String(options.icon || "star"), color = normalizedColor(options.color, [1, 1, 1]);
            app.beginUndoGroup("TonyFX Add Icon");
            var layer = comp.layers.addShape(); layer.name = "TonyFX Icon - " + name;
            var root = layer.property("ADBE Root Vectors Group"), geometry = iconGeometry(name, size);
            for (var i = 0; i < geometry.length; i++) { addIconPolygon(root, geometry[i], color); }
            layer.property("ADBE Transform Group").property("ADBE Position").setValue([comp.width / 2, comp.height / 2]);
            layer.label = 11; layer.selected = true;
            app.endUndoGroup();
            return response({ok:true,message:"Added editable " + name + " vector icon at comp center."});
        } catch (error) { try { app.endUndoGroup(); } catch (ignore) {} return response({ok:false,error:error.toString()}); }
    };

    function layerSourceTimes(layer, first, last, frameDuration) {
        var sourceAtIn, sourceAtOut, remapped = !!layer.timeRemapEnabled;
        if (remapped) {
            var remap = layer.property("ADBE Time Remapping");
            if (!remap) { throw new Error("TonyFX could not read the selected layer's time remap."); }
            sourceAtIn = Number(remap.valueAtTime(first, false));
            sourceAtOut = Number(remap.valueAtTime(Math.max(first, last - frameDuration * 0.5), false));
        } else {
            var stretch = Number(layer.stretch) || 100, rate = 100 / stretch;
            sourceAtIn = (first - layer.startTime) * rate;
            sourceAtOut = (last - layer.startTime) * rate;
        }
        return {first:sourceAtIn,last:sourceAtOut,reverse:sourceAtOut<sourceAtIn,timeRemapped:remapped};
    }

    function resolveLocalMediaRange(layer, first, last, frameDuration, depth) {
        if (depth > 8) { throw new Error("TonyFX reached the nested precomp limit."); }
        if (!layer.source) { throw new Error("The selected layer has no media source."); }
        var timing = layerSourceTimes(layer, first, last, frameDuration);
        if (layer.source.file) {
            var fileStart = Math.max(0, Math.min(timing.first, timing.last));
            var fileEnd = Math.max(timing.first, timing.last);
            try { fileEnd = Math.min(Number(layer.source.duration) || fileEnd, fileEnd); } catch (ignoreFileDuration) {}
            return {file:layer.source.file,start:fileStart,end:fileEnd,reverse:timing.reverse,timeRemapped:timing.timeRemapped};
        }
        if (!(layer.source instanceof CompItem)) { throw new Error("The selected layer must reference local footage or a scene precomp containing local footage."); }
        var nestedComp = layer.source;
        var nestedStart = Math.max(0, Math.min(timing.first, timing.last));
        var nestedEnd = Math.min(nestedComp.duration, Math.max(timing.first, timing.last));
        var best = null, bestOverlap = 0;
        for (var i = 1; i <= nestedComp.numLayers; i++) {
            var candidate = nestedComp.layer(i);
            if (!candidate.source || candidate.adjustmentLayer || candidate.nullLayer || candidate.enabled === false) { continue; }
            var overlap = Math.max(0, Math.min(nestedEnd, candidate.outPoint) - Math.max(nestedStart, candidate.inPoint));
            if (overlap > bestOverlap && (candidate.source.file || candidate.source instanceof CompItem)) { best = candidate; bestOverlap = overlap; }
        }
        if (!best) { throw new Error("The selected precomp has no active local footage in its visible range."); }
        var resolved = resolveLocalMediaRange(best, Math.max(nestedStart, best.inPoint), Math.min(nestedEnd, best.outPoint), nestedComp.frameDuration, depth + 1);
        if (timing.reverse) { resolved.reverse = !resolved.reverse; }
        resolved.timeRemapped = timing.timeRemapped || resolved.timeRemapped;
        return resolved;
    }

    function ensureFolderPath(pathValue) {
        var folder = new Folder(pathValue);
        if (folder.exists) { return folder; }
        var parent = folder.parent;
        if (parent && !parent.exists) { ensureFolderPath(parent.fsName); }
        if (!folder.create() && !folder.exists) { throw new Error("TonyFX could not create its composition-render folder: " + folder.fsName); }
        return folder;
    }

    function safeMediaName(value) {
        var name = String(value || "composition").replace(/[\\\/:*?\"<>|]+/g, "-").replace(/^\s+|\s+$/g, "");
        return name.substring(0, 72) || "composition";
    }

    function renderCompositionIntermediate(sourceComp, rangeStart, rangeDuration, outputRoot) {
        if (app.project.renderQueue.rendering) { throw new Error("After Effects is already rendering. Finish that render before preparing a TonyFX composition."); }
        var folder = ensureFolderPath(outputRoot + "/inputs"), stamp = String(new Date().getTime());
        var outputFile = new File(folder.fsName + "/" + safeMediaName(sourceComp.name) + "_TonyFX_Source_" + stamp + ".avi");
        var queue = app.project.renderQueue, previous = [], item = null;
        try {
            for (var i = 1; i <= queue.numItems; i++) { previous.push({item:queue.item(i),render:queue.item(i).render}); }
            item = queue.items.add(sourceComp);
            try { item.applyTemplate("Best Settings"); } catch (ignoreRenderTemplate) {}
            item.timeSpanStart = Math.max(0, Math.min(sourceComp.duration, Number(rangeStart) || 0));
            item.timeSpanDuration = Math.max(sourceComp.frameDuration, Math.min(sourceComp.duration - item.timeSpanStart, Number(rangeDuration) || sourceComp.duration));
            var outputModule = item.outputModule(1);
            try { outputModule.applyTemplate("Lossless"); } catch (ignoreOutputTemplate) {}
            outputModule.file = outputFile;
            for (var p = 0; p < previous.length; p++) { try { previous[p].item.render = false; } catch (ignoreDisable) {} }
            item.render = true;
            queue.render();
            if (!outputFile.exists || outputFile.length <= 0) { throw new Error("After Effects did not create the TonyFX composition intermediate."); }
            return {file:outputFile,start:item.timeSpanStart,duration:item.timeSpanDuration};
        } finally {
            if (item) { try { item.remove(); } catch (ignoreRemoveQueueItem) {} }
            for (var r = 0; r < previous.length; r++) { try { previous[r].item.render = previous[r].render; } catch (ignoreRestore) {} }
        }
    }

    api.getEnhanceSourceSelection = function (json) {
        try {
            var options = parseJSON(json), mode = options.mode === "composition" ? "composition" : "clips";
            var comp = activeComp(), layers = selectedLayers(comp).slice(0), items = [];
            if (mode === "clips") {
                if (!layers.length) { throw new Error("Select one or more video layers to enhance."); }
                layers.sort(function (a, b) { return a.inPoint - b.inPoint || a.index - b.index; });
                for (var i = 0; i < layers.length; i++) {
                    var layer = layers[i];
                    if (!layer.source || layer.adjustmentLayer || layer.nullLayer) { continue; }
                    var resolved = resolveLocalMediaRange(layer, layer.inPoint, layer.outPoint, comp.frameDuration, 0);
                    items.push({path:resolved.file.fsName,layerName:layer.name,layerIndex:layer.index,compIn:layer.inPoint,compOut:layer.outPoint,compDuration:layer.outPoint-layer.inPoint,sourceStart:resolved.start,sourceDuration:Math.max(comp.frameDuration,resolved.end-resolved.start),reverse:resolved.reverse,timeRemapped:resolved.timeRemapped,fromPrecomp:layer.source instanceof CompItem});
                }
                if (!items.length) { throw new Error("The selected layers do not contain local video footage."); }
                return response({ok:true,mode:mode,label:items.length + " selected clip" + (items.length === 1 ? "" : "s"),message:"Ready to enhance " + items.length + " clip" + (items.length === 1 ? "" : "s") + " sequentially and align every result.",items:items});
            }

            var sourceComp, sourceStart, sourceDuration, compIn;
            if (layers.length === 0) {
                sourceComp = comp;
                sourceStart = Math.max(0, Number(comp.workAreaStart) || 0);
                sourceDuration = Math.max(comp.frameDuration, Number(comp.workAreaDuration) || comp.duration);
                compIn = sourceStart;
            } else if (layers.length === 1 && layers[0].source instanceof CompItem) {
                var precompLayer = layers[0], timing = layerSourceTimes(precompLayer, precompLayer.inPoint, precompLayer.outPoint, comp.frameDuration);
                sourceComp = precompLayer.source;
                sourceStart = Math.max(0, Math.min(timing.first,timing.last));
                sourceDuration = Math.max(sourceComp.frameDuration, Math.min(sourceComp.duration,Math.max(timing.first,timing.last))-sourceStart);
                compIn = precompLayer.inPoint;
            } else {
                throw new Error("For Whole Composition, select exactly one precomp layer, or deselect every layer to render the active composition work area.");
            }
            var rendered = renderCompositionIntermediate(sourceComp,sourceStart,sourceDuration,String(options.engineRoot || Folder.myDocuments.fsName + "/TonyFX Local Engine"));
            items.push({path:rendered.file.fsName,layerName:sourceComp.name,compIn:compIn,compOut:compIn+rendered.duration,compDuration:rendered.duration,sourceStart:0,sourceDuration:rendered.duration,renderedComposition:true});
            return response({ok:true,mode:mode,label:sourceComp.name,message:"Rendered the complete composition range with effects and audio. Ready to enhance as one video.",items:items});
        } catch (error) { return response({ok:false,error:error.toString() + (error.line ? " at line " + error.line : "")}); }
    };

    api.getCaptionSourceSelection = function () {
        try {
            var comp = activeComp(), layers = selectedLayers(comp);
            if (layers.length !== 1) { throw new Error("Select exactly one video or audio layer for transcription."); }
            var layer = layers[0];
            var resolved = resolveLocalMediaRange(layer, layer.inPoint, layer.outPoint, comp.frameDuration, 0);
            var sourceDuration = Math.max(comp.frameDuration, resolved.end - resolved.start);
            return response({ok:true,path:resolved.file.fsName,layerName:layer.name,compIn:layer.inPoint,compOut:layer.outPoint,compDuration:layer.outPoint-layer.inPoint,sourceStart:resolved.start,sourceDuration:sourceDuration,reverse:resolved.reverse,timeRemapped:resolved.timeRemapped,fromPrecomp:layer.source instanceof CompItem});
        } catch (error) { return response({ok:false,error:error.toString()}); }
    };

    function captionSelectorProperty(selector, names) {
        for (var i = 0; i < names.length; i++) {
            var property = selector.property(names[i]);
            if (property) { return property; }
        }
        return null;
    }

    function revealCaptionWords(comp, property, words, start, end) {
        var valid = [], i;
        for (i = 0; i < (words || []).length; i++) {
            var wordStart = Math.max(start, Number(words[i].start) || start);
            var wordEnd = Math.min(end, Math.max(wordStart + comp.frameDuration, Number(words[i].end) || wordStart + comp.frameDuration * 3));
            if (wordStart < end) { valid.push({start:wordStart,end:wordEnd}); }
        }
        if (!valid.length) { return false; }
        clearKeys(property); property.setValue(0);
        var step = 100 / valid.length;
        for (i = 0; i < valid.length; i++) {
            var revealStart = Math.max(start, Math.min(end - comp.frameDuration, valid[i].start));
            var revealEnd = Math.min(valid[i].end, revealStart + comp.frameDuration * 3);
            if (revealEnd <= revealStart) { revealEnd = Math.min(end, revealStart + comp.frameDuration); }
            property.setValueAtTime(revealStart, i * step);
            property.setValueAtTime(revealEnd, (i + 1) * step);
        }
        property.setValueAtTime(Math.max(start, end - comp.frameDuration * 0.25), 100);
        for (i = 1; i <= property.numKeys; i++) {
            try {
                if (i % 2 === 1) {
                    temporalEase(property, i, 18, 55, 0, 0);
                    property.setInterpolationTypeAtKey(i, KeyframeInterpolationType.HOLD, KeyframeInterpolationType.BEZIER);
                } else {
                    temporalEase(property, i, 55, 18, 0, 0);
                    property.setInterpolationTypeAtKey(i, KeyframeInterpolationType.BEZIER, KeyframeInterpolationType.HOLD);
                }
            } catch (ignoreWordEase) {}
        }
        return true;
    }

    function captionMotionSpec(animation) {
        var map = {
            wordFade:{id:"text-word-fade",name:"Caption Word Fade",mode:"opacity",unit:"words",duration:18,smoothness:62},
            letterFade:{id:"text-char-fade",name:"Caption Letter Fade",mode:"opacity",unit:"characters",duration:20,smoothness:22},
            pop:{id:"text-scale-pop",name:"Caption Soft Pop",mode:"scale",unit:"words",duration:18,smoothness:26},
            scalePunch:{id:"text-scale-punch",name:"Caption Scale Punch",mode:"scalePunch",unit:"words",duration:18,smoothness:13},
            wipeLeft:{id:"text-wipe-left",name:"Caption Wipe Left",mode:"wipe",direction:"left",unit:"characters",duration:20,smoothness:4},
            wipeRight:{id:"text-wipe-right",name:"Caption Wipe Right",mode:"wipe",direction:"right",unit:"characters",duration:20,smoothness:4},
            blurReveal:{id:"text-blur-reveal",name:"Caption Blur Reveal",mode:"blur",unit:"words",duration:20,smoothness:44},
            trackingTight:{id:"text-tighten",name:"Caption Tracking Tighten",mode:"trackingTight",unit:"characters",duration:22,smoothness:34},
            waveRise:{id:"text-wave-rise",name:"Caption Wave Rise",mode:"wave",unit:"characters",duration:22,smoothness:46}
        };
        var options = map[animation] || map.wordFade;
        var spec = textMotionSpec(options);
        if (animation === "wordFade") { spec.wordSync = true; }
        if (animation === "pop") { spec.wordSync = true; }
        if (animation === "blurReveal") { spec.wordSync = true; }
        if (animation === "flipX") {
            spec = textMotionSpec({id:"caption-flip-x",name:"Caption 3D Flip X",unit:"characters",duration:20,smoothness:18});
            spec.rotationX=92; spec.position=[0,24,-120]; spec.blur=5; spec.opacity=0; spec.perCharacter3D=true;
        } else if (animation === "flipY") {
            spec = textMotionSpec({id:"caption-flip-y",name:"Caption 3D Flip Y",unit:"characters",duration:20,smoothness:18});
            spec.rotationY=-92; spec.position=[-24,0,-120]; spec.blur=5; spec.opacity=0; spec.perCharacter3D=true;
        } else if (animation === "depthPush") {
            spec = textMotionSpec({id:"caption-depth-push",name:"Caption 3D Depth Push",unit:"characters",duration:22,smoothness:26});
            spec.position=[0,0,-360]; spec.scale=[48,48,100]; spec.blur=14; spec.opacity=0; spec.perCharacter3D=true;
        }
        return spec;
    }

    function applyCaptionAnimator(comp, layer, animation, start, end, words, motionOptions) {
        if (animation === "none") { removeTonyFxTextMotion(layer,true); return; }
        removeTonyFxTextMotion(layer,true);
        var spec = captionMotionSpec(animation);
        // Captions must land quickly enough to remain readable. Stretching the
        // selector across the entire caption made every preset look like a
        // faint fade and left later words moving until the layer disappeared.
        var revealEnd = Math.min(end - comp.frameDuration, start + frameTime(comp,spec.duration));
        if (revealEnd <= start) { revealEnd = Math.min(end,start + comp.frameDuration); }
        if (buildTextMotionAnimator(comp,layer,spec,start,revealEnd,words)) {
            motionOptions=motionOptions||{};
            addMatchedTextExit(comp,layer,spec,revealEnd,{matchedExit:motionOptions.matchedExit!==false,exitDuration:Math.max(6,Number(motionOptions.exitDuration)||Math.max(8,spec.duration))});
        }
    }

    function mappedCaptionTime(comp, seconds, options) {
        var base = Number(options.compIn) || 0;
        var sourceDuration = Math.max(comp.frameDuration, Number(options.sourceDuration) || 0);
        var compDuration = Math.max(comp.frameDuration, Number(options.compDuration) || sourceDuration);
        var value = Math.max(0, Math.min(sourceDuration, Number(seconds) || 0));
        var mapped = options.reverse ? base + (sourceDuration - value) * (compDuration / sourceDuration) : base + value * (compDuration / sourceDuration);
        return Math.max(0, Math.min(comp.duration, Math.round(mapped / comp.frameDuration) * comp.frameDuration));
    }

    function captionTimelineRange(comp, item, options) {
        var a = Math.max(0, Number(item.start) || 0), b = Math.max(a, Number(item.end) || a);
        var start = mappedCaptionTime(comp, options.reverse ? b : a, options);
        var end = mappedCaptionTime(comp, options.reverse ? a : b, options);
        if (end < start) { var swap = start; start = end; end = swap; }
        if (end < start + comp.frameDuration * 2) { end = Math.min(comp.duration, start + comp.frameDuration * 2); }
        var mappedWords = [], sourceWords = item.words || [];
        for (var w = 0; w < sourceWords.length; w++) {
            var wordStart = mappedCaptionTime(comp, options.reverse ? sourceWords[w].end : sourceWords[w].start, options);
            var wordEnd = mappedCaptionTime(comp, options.reverse ? sourceWords[w].start : sourceWords[w].end, options);
            if (wordEnd < wordStart) { var wordSwap = wordStart; wordStart = wordEnd; wordEnd = wordSwap; }
            mappedWords.push({text:String(sourceWords[w].text || sourceWords[w].word || ""),start:wordStart,end:Math.max(wordStart + comp.frameDuration,wordEnd)});
        }
        mappedWords.sort(function (left,right) { return left.start - right.start; });
        return {start:start,end:end,text:String(item.text || "").replace(/^\s+|\s+$/g, ""),words:mappedWords};
    }

    api.createCaptions = function (json) {
        try {
            var options = parseJSON(json), comp = activeComp(), captions = options.captions || [];
            if (!captions.length) { throw new Error("The transcription returned no caption phrases."); }
            var placement = options.placement === "center" ? 0.56 : 0.82;
            var fontSize = Math.max(18, Math.min(160, Number(options.fontSize) || 48));
            var style = options.style || {font:options.font || "Arial-BoldMT",fontSize:fontSize,fill:[1,1,1],strokeEnabled:false,stroke:[0,0,0],strokeWidth:0,shadowEnabled:true,shadowColor:[0,0,0],shadowOpacity:68,shadowDirection:135,shadowDistance:8,shadowSoftness:22,glowEnabled:false,glowIntensity:0,glowRadius:0};
            style.fontSize = fontSize;
            var mapped = [];
            for (var m = 0; m < captions.length; m++) {
                var mappedItem = captionTimelineRange(comp, captions[m], options);
                if (mappedItem.text) { mapped.push(mappedItem); }
            }
            mapped.sort(function (a, b) { return a.start - b.start; });
            for (var q = 0; q < mapped.length - 1; q++) {
                if (mapped[q].end > mapped[q + 1].start) { mapped[q].end = Math.max(mapped[q].start + comp.frameDuration * 2, mapped[q + 1].start); }
            }
            app.beginUndoGroup("TonyFX Create Offline Captions");
            for (var l = 1; l <= comp.numLayers; l++) { comp.layer(l).selected = false; }
            for (var i = mapped.length - 1; i >= 0; i--) {
                var item = mapped[i], textValue = item.text, start = item.start, end = item.end;
                var layer = comp.layers.addText(textValue), sourceText = layer.property("ADBE Text Properties").property("ADBE Text Document"), doc = sourceText.value;
                if (options.language === "ar") { style.font = "Arial-BoldMT"; }
                applyTextStyleToLayer(layer, style);
                doc = sourceText.value; doc.justification = ParagraphJustification.CENTER_JUSTIFY;
                sourceText.setValue(doc);
                layer.name = "CAPTION " + (i + 1) + " - " + textValue.substring(0, 28);
                layer.startTime = 0; layer.inPoint = start; layer.outPoint = end;
                layer.property("ADBE Transform Group").property("ADBE Position").setValue([comp.width / 2, comp.height * placement]);
                applyCaptionAnimator(comp, layer, options.animation || "wordFade", start, end, item.words || [], options);
                if (options.textEffect && String(options.textEffect.id || "none") !== "none") {
                    var effectFrames = Math.max(4, Math.min(90, Number(options.textEffect.duration) || 18));
                    applyTextEffectToLayer(comp, layer, options.textEffect, start, Math.min(end, start + effectFrames * comp.frameDuration));
                }
                layer.label = 10; layer.selected = true;
            }
            app.endUndoGroup();
            return response({ok:true,message:"Created " + mapped.length + " frame-aligned offline caption layers.",language:options.language || "auto"});
        } catch (error) { try { app.endUndoGroup(); } catch (ignore) {} return response({ok:false,error:error.toString() + (error.line ? " at line " + error.line : "")}); }
    };

    function offlineLayerHasVideo(layer) {
        if(!layer || !layer.source || layer.adjustmentLayer || layer.nullLayer){return false;}
        try{if(layer.hasVideo===true){return true;}}catch(ignoreHasVideo){}
        try{return Number(layer.source.width)>0&&Number(layer.source.height)>0;}catch(ignoreDimensions){return false;}
    }

    function offlineBuilderSources(comp) {
        var selected = selectedLayers(comp), sources = [], i, layer;
        for (i = 0; i < selected.length; i++) {
            layer = selected[i];
            if (offlineLayerHasVideo(layer) && !isProtected(layer)) { sources.push(layer); }
        }
        if (!sources.length) {
            for (i = 1; i <= comp.numLayers; i++) {
                layer = comp.layer(i);
                if (offlineLayerHasVideo(layer) && !isProtected(layer) && layer.enabled !== false) { sources.push(layer); }
            }
        }
        sources.sort(function (left,right) { return left.inPoint === right.inPoint ? left.index - right.index : left.inPoint - right.inPoint; });
        return sources;
    }

    function offlineMotionTile(layer) {
        var effects = layer.property("ADBE Effect Parade"), tile = effectByMatchOrName(effects, "ADBE Tile", /motion tile/i);
        if (!tile) { try { tile = effects.addProperty("ADBE Tile"); } catch (ignoreTile) {} }
        if (tile) { tile.name = "TonyFX - Motion Tile 200 Reflect"; setProperty(tile,["ADBE Tile-0004","Output Width"],200); setProperty(tile,["ADBE Tile-0005","Output Height"],200); setProperty(tile,["ADBE Tile-0011","Mirror Edges"],true); }
    }

    function offlineWords(value) {
        return String(value || "").toLowerCase().replace(/[^a-z0-9_]+/g," ").split(/\s+/);
    }

    function offlineCandidateText(layer) {
        var text=String(layer.name || "");
        try {
            if (layer.source) {
                text += " " + String(layer.source.name || "");
                if (layer.source.file) { text += " " + String(layer.source.file.fsName || ""); }
            }
        } catch(ignoreSourceName) {}
        return text.toLowerCase();
    }

    function offlineMatchNames(shot) {
        var matches=shot && (shot.footageMatches || (shot.semantic && shot.semantic.rankedProjectMatches)) || [];
        var result=[];
        for(var i=0;i<Math.min(5,matches.length);i++) {
            var match=matches[i]||{}, values=[match.layerName,match.name,match.path,match.sourceName];
            for(var x=0;x<values.length;x++){var value=String(values[x]||"").toLowerCase();if(value){result.push(value);}}
        }
        return result;
    }

    function offlineChooseSource(candidates, shot, used, previousIndex, shotIndex) {
        var exact=offlineMatchNames(shot), semantic=shot && shot.semantic || {}, keywords=semantic.keywords || [];
        var best=-1, bestScore=-9999;
        for (var i=0;i<candidates.length;i++) {
            var name=offlineCandidateText(candidates[i]), score=0;
            for(var m=0;m<exact.length;m++){
                if(name===exact[m] || name.indexOf(exact[m])>=0 || exact[m].indexOf(name)>=0){score+=Math.max(25,110-m*18);break;}
            }
            for (var k=0;k<keywords.length;k++) { var word=String(keywords[k]||"").toLowerCase(); if (word && name.indexOf(word)>=0) { score+=8; } }
            if (semantic.role && name.indexOf(String(semantic.role).toLowerCase())>=0) { score+=10; }
            try { if(candidates[i].outPoint-candidates[i].inPoint < Math.max(0.12,Number(shot.duration)||0)){score-=20;} } catch(ignoreDuration){}
            score-=Number(used[i]||0)*15;
            if (i===previousIndex) { score-=55; }
            // Stable tie breaker rotates through the source pool, so rerunning
            // a blueprint does not collapse onto the first few layers.
            score-=Math.abs(i-(shotIndex%candidates.length))*0.02;
            if (score>bestScore) { bestScore=score; best=i; }
        }
        return best<0 ? shotIndex%candidates.length : best;
    }

    function offlineClamp(value,min,max,fallback) {
        var number=Number(value);if(!isFinite(number)){number=Number(fallback)||0;}return Math.max(min,Math.min(max,number));
    }

    function offlineNormalizePolicy(options) {
        var source=options && options.policy || {}, disabled=source.disabledFamilies || [], cleanDisabled=[], i;
        for(i=0;i<disabled.length;i++){var family=String(disabled[i]||"").toLowerCase();if(family&&cleanDisabled.indexOf(family)<0){cleanDisabled.push(family);}}
        return {
            version:3,mode:/^(exact|balanced|creative)$/.test(String(source.mode||""))?String(source.mode):"exact",prompt:String(source.prompt||""),seed:Math.round(offlineClamp(source.seed,1,9999,1)),
            fidelity:offlineClamp(source.fidelity,0.5,1,0.92),intensity:offlineClamp(source.intensity,0.5,1.6,1),transitionDensity:offlineClamp(source.transitionDensity,0,1,0.85),
            noRepeatWindow:Math.round(offlineClamp(source.noRepeatWindow,1,12,5)),keepExactCuts:source.keepExactCuts!==false,autoQA:source.autoQA!==false,
            creativeAccents:source.creativeAccents===true,creativeAmount:offlineClamp(source.creativeAmount,0,1,0),disabledFamilies:cleanDisabled,familyIntensity:source.familyIntensity||{},
            durationScale:offlineClamp(source.durationScale,0.55,1.5,1),zoomStrength:offlineClamp(source.zoomStrength,0.55,1.45,1),zoomPattern:String(source.zoomPattern||"energy_alternate"),
            avoidRepeats:source.avoidRepeats!==false,subjectBias:String(source.subjectBias||"").toLowerCase(),changeShots:source.changeShots||[],changeRange:source.changeRange||{start:null,end:null},
            freezeClips:source.freezeClips===true,freezeOutsideRange:source.freezeOutsideRange===true
        };
    }

    function offlineFps(value,fallback) {
        var text=String(value||""),parts=text.split("/"),fps;
        if(parts.length===2){fps=Number(parts[0])/Math.max(0.000001,Number(parts[1]));}
        else{fps=Number(value);}
        return isFinite(fps)&&fps>0?fps:Math.max(1,Number(fallback)||30);
    }

    function offlineMergeContractShot(legacy,contract,fps) {
        var result={},key,frames=contract&&contract.compFrames||[];
        legacy=legacy||{};contract=contract||{};
        for(key in legacy){if(legacy.hasOwnProperty(key)){result[key]=legacy[key];}}
        for(key in contract){if(contract.hasOwnProperty(key)){result[key]=contract[key];}}
        if(frames.length===2){result.startTime=Number(frames[0])/fps;result.endTime=Number(frames[1])/fps;result.duration=result.endTime-result.startTime;result.durationFrames=Number(frames[1])-Number(frames[0]);}
        return result;
    }

    function offlineContractShots(blueprint,contract,fps) {
        var legacy=blueprint&&blueprint.shots||[],strict=contract&&contract.shots||[],result=[],count=Math.max(legacy.length,strict.length);
        for(var i=0;i<count;i++){result.push(offlineMergeContractShot(legacy[i],strict[i],fps));}
        return result;
    }

    function offlineContractTransitions(blueprint,contract,fps) {
        var source=contract&&contract.transitions&&contract.transitions.length?contract.transitions:(blueprint&&blueprint.transitions||[]),result=[];
        for(var i=0;i<source.length;i++){
            var item=source[i]||{},copy={},key,frames=item.frames||item.span||[];
            for(key in item){if(item.hasOwnProperty(key)){copy[key]=item[key];}}
            if(copy.cutFrame!==undefined){copy.frame=Number(copy.cutFrame);copy.time=Number(copy.cutFrame)/fps;}
            if(frames.length===2){copy.startFrame=Number(frames[0]);copy.endFrame=Math.max(Number(frames[0]),Number(frames[1])-1);copy.durationFrames=Number(frames[1])-Number(frames[0]);}
            if(copy.families&&!copy.measuredFamilies){copy.measuredFamilies=copy.families;}
            if(copy.curve&&copy.curve.controls){copy.advancedCurve={controls:copy.curve.controls,confidence:copy.confidence||1};copy.curveSource=copy.curve.source||"replica builder contract";}
            result.push(copy);
        }
        return result;
    }

    function offlineReplicaContractIssues(contract) {
        var issues=[],gate=contract&&contract.buildGate||{},shots=contract&&contract.shots||[],transitions=contract&&contract.transitions||[],i,frames,zoom,curve;
        if(!contract||contract.schema!=="tonyfx.replica-builder-contract.v1"){issues.push("missing tonyfx.replica-builder-contract.v1");return issues;}
        if(!contract.certificate||!contract.certificate.sha256){issues.push("missing analysis-bound certificate");}
        if(!gate.exactReady){issues.push("analysis build gate is blocked: "+String((gate.blockingCodes||[]).join(", ")||"unresolved ambiguity"));}
        if(!shots.length){issues.push("no frame-native shots");}
        for(i=0;i<shots.length;i++){
            frames=shots[i].compFrames||[];if(frames.length!==2||Number(frames[0])>=Number(frames[1])){issues.push("invalid shot frame range "+(i+1));}
            zoom=shots[i].motionPlan&&shots[i].motionPlan.zoom||{};if(zoom.enabled&&(!zoom.curve||!zoom.curve.controls||zoom.owner!=="scene")){issues.push("shot "+(i+1)+" has an uncertified scene zoom");}
        }
        for(i=0;i<transitions.length;i++){
            curve=transitions[i].curve;var families=transitions[i].families||[];
            if(transitions[i].supported===false){issues.push("unsupported transition "+(i+1));}
            var needsCurve=false;for(var f=0;f<families.length;f++){if(String(families[f]).toLowerCase()!=="hard_cut"&&String(families[f]).toLowerCase()!=="cut"){needsCurve=true;}}
            if(needsCurve&&(!curve||!curve.controls)){issues.push("transition "+(i+1)+" is missing its measured curve");}
        }
        return issues;
    }

    function offlineStableNoise(seed,shotIndex,candidateIndex) {
        var value=Math.sin((seed+17)*(shotIndex+3)*12.9898+(candidateIndex+11)*78.233)*43758.5453;
        return (value-Math.floor(value))-0.5;
    }

    function offlinePreviousCandidate(candidates,assignment) {
        if(!assignment){return -1;}var wanted=String(assignment.sourceName||assignment.layerName||assignment.name||"").toLowerCase();
        if(!wanted && assignment.sourceIndex!==undefined){var direct=Number(assignment.sourceIndex);return direct>=0&&direct<candidates.length?direct:-1;}
        for(var i=0;i<candidates.length;i++){var text=offlineCandidateText(candidates[i]);if(text===wanted||text.indexOf(wanted)>=0||wanted.indexOf(text)>=0){return i;}}
        return -1;
    }

    function offlineShotCanChange(policy,shotIndex,shot) {
        if(!policy.freezeOutsideRange){return true;}var number=shotIndex+1,time=Number(shot.startTime)||0,i;
        if(policy.changeShots&&policy.changeShots.length){for(i=0;i<policy.changeShots.length;i++){if(Number(policy.changeShots[i])===number){return true;}}return false;}
        if(policy.changeRange&&policy.changeRange.start!==null&&time<Number(policy.changeRange.start)){return false;}
        if(policy.changeRange&&policy.changeRange.end!==null&&time>Number(policy.changeRange.end)){return false;}
        return true;
    }

    function offlineSourceIsContinuous(layer) {
        try{if(layer.source instanceof FootageItem){return true;}}catch(ignoreFootage){}
        try{
            if(layer.source instanceof CompItem){
                var visible=0;
                for(var i=1;i<=layer.source.numLayers;i++){var nested=layer.source.layer(i);if(offlineLayerHasVideo(nested)&&nested.enabled!==false){visible++;}}
                return visible===1;
            }
        }catch(ignoreComp){}
        return false;
    }

    function offlineBestCandidateMatch(layer,shot) {
        var matches=shot&&shot.footageMatches||(shot&&shot.semantic&&shot.semantic.rankedProjectMatches)||[],text=offlineCandidateText(layer),best=null,bestScore=-1;
        for(var i=0;i<matches.length;i++){
            var item=matches[i]||{},values=[item.layerName,item.name,item.path,item.sourceName],matched=false;
            for(var x=0;x<values.length;x++){var value=String(values[x]||"").toLowerCase();if(value&&(text.indexOf(value)>=0||value.indexOf(text)>=0)){matched=true;break;}}
            if(matched){var score=Number(item.confidence)||0;if(score>bestScore){bestScore=score;best=item;}}
        }
        return best;
    }

    function offlineCandidateMatchConfidence(layer,shot) {
        var match=offlineBestCandidateMatch(layer,shot);return match?Number(match.confidence)||0:-1;
    }

    function offlineMatchedSourceWindow(layer,shot,need) {
        var match=offlineBestCandidateMatch(layer,shot),stretch=Math.abs(Number(layer.stretch)||100)/100;
        var layerStart=Math.max(0,(Number(layer.inPoint)-Number(layer.startTime))*stretch),layerDuration=Math.max(0,(Number(layer.outPoint)-Number(layer.inPoint))*stretch);
        var rangeStart=match&&isFinite(Number(match.sourceStart))?Math.max(0,Number(match.sourceStart)):layerStart;
        var rangeDuration=match&&isFinite(Number(match.sourceDuration))&&Number(match.sourceDuration)>0?Number(match.sourceDuration):layerDuration;
        var center=match&&isFinite(Number(match.time))?Number(match.time):rangeStart+Math.min(rangeDuration,need)/2;
        var available=Math.max(0,rangeDuration),latest=Math.max(rangeStart,rangeStart+available-Math.max(0,need));
        var sourceIn=Math.max(rangeStart,Math.min(latest,center-Math.max(0,need)/2));
        return {matched:!!match,match:match,sourceIn:sourceIn,sourceSpan:Math.max(0,Math.min(available,need)),available:available,confidence:match?Number(match.confidence)||0:-1,motionScore:match?Number(match.motionScore)||0:0};
    }

    function offlineAssignmentIssues(candidates,shots,picks,repeatByShot,repeatDirectionByShot,policy,fps) {
        var issues=[],recent=[],frame=1/Math.max(1,fps),i,index,layer,shot,need,available,confidence,requirements,matchWindow;
        if(policy.mode!=="exact"){return issues;}
        for(i=0;i<shots.length;i++){
            index=Number(picks[i]);layer=candidates[index];shot=shots[i]||{};requirements=shot.sourceRequirements||{};
            if(!layer){issues.push("shot "+(i+1)+" has no source assignment");continue;}
            need=Math.max(frame,Number(shot.endTime)-Number(shot.startTime)||Number(shot.duration)||frame);
            available=Math.max(0,Number(layer.outPoint)-Number(layer.inPoint));
            if(available+frame*0.1<need){issues.push("shot "+(i+1)+" source is too short at native speed");}
            if(requirements.continuousShotRequired!==false&&!offlineSourceIsContinuous(layer)){issues.push("shot "+(i+1)+" is not verified as one continuous camera angle");}
            if(String(repeatDirectionByShot&&repeatDirectionByShot[i+1]||"").toLowerCase()==="reverse"){try{if(layer.canSetTimeRemapEnabled!==true){issues.push("shot "+(i+1)+" cannot preserve the measured reverse playback");}}catch(ignoreCanReverse){issues.push("shot "+(i+1)+" cannot verify reverse playback support");}}
            confidence=offlineCandidateMatchConfidence(layer,shot);
            if((shot.footageMatches||[]).length&&confidence<Number(requirements.minimumMatchConfidence||0.42)){issues.push("shot "+(i+1)+" does not use an evidence-ranked footage match");}
            matchWindow=offlineMatchedSourceWindow(layer,shot,need);
            if(requirements.matchedSourceWindowRequired===true&&!matchWindow.matched){issues.push("shot "+(i+1)+" has no executable vision-matched source moment");}
            if(matchWindow.matched&&matchWindow.available+frame*0.1<need){issues.push("shot "+(i+1)+" vision-matched source window is too short");}
            if(Number(requirements.minimumMotionScore||0)>0&&matchWindow.motionScore+0.0001<Number(requirements.minimumMotionScore)){issues.push("shot "+(i+1)+" is a music-peak slot but its matched footage is too calm");}
            if(!repeatByShot[i+1]){
                for(var r=Math.max(0,recent.length-policy.noRepeatWindow);r<recent.length;r++){if(recent[r]===index){issues.push("shot "+(i+1)+" repeats source outside the reference repeat topology");break;}}
            }
            recent.push(index);
        }
        return issues;
    }

    function offlineCandidateScore(candidates,candidateIndex,shot,state,shotIndex,policy) {
        var layer=candidates[candidateIndex],name=offlineCandidateText(layer),exact=offlineMatchNames(shot),semantic=shot&&shot.semantic||{},keywords=semantic.keywords||[],score=0,i;
        for(i=0;i<exact.length;i++){if(name===exact[i]||name.indexOf(exact[i])>=0||exact[i].indexOf(name)>=0){score+=Math.max(28,126-i*19)*policy.fidelity;break;}}
        for(i=0;i<keywords.length;i++){var word=String(keywords[i]||"").toLowerCase();if(word&&name.indexOf(word)>=0){score+=8*policy.fidelity;}}
        if(semantic.role&&name.indexOf(String(semantic.role).toLowerCase())>=0){score+=12*policy.fidelity;}
        if(policy.subjectBias&&name.indexOf(policy.subjectBias)>=0){score+=38;}
        try{var need=Math.max(0.12,Number(shot.duration)||Number(shot.endTime)-Number(shot.startTime)||0);if(layer.outPoint-layer.inPoint<need){score-=policy.mode==="exact"?100000:35;}}catch(ignoreDuration){}
        if(policy.mode==="exact"&&!offlineSourceIsContinuous(layer)){score-=5000;}
        var matchConfidence=offlineCandidateMatchConfidence(layer,shot);
        if(matchConfidence>=0){score+=matchConfidence*(policy.mode==="exact"?220:90);}else if(policy.mode==="exact"&&(shot.footageMatches||[]).length){score-=900;}
        score-=Number(state.counts[candidateIndex]||0)*(policy.avoidRepeats?13:5);
        for(i=Math.max(0,state.picks.length-policy.noRepeatWindow);i<state.picks.length;i++){if(state.picks[i]===candidateIndex){score-=58+(i===state.picks.length-1?75:0);}}
        score+=offlineStableNoise(policy.seed,shotIndex,candidateIndex)*(policy.mode==="creative"?8:1);
        return score;
    }

    function offlinePlanSources(candidates,shots,repeatByShot,policy,previousAssignments) {
        var beam=[{score:0,picks:[],counts:[]}],beamWidth=policy.mode==="creative"?22:14,i,s,c,next,forced,shot,previous;
        for(i=0;i<candidates.length;i++){beam[0].counts.push(0);}
        for(i=0;i<shots.length;i++){
            shot=shots[i];next=[];forced=-1;previous=previousAssignments&&previousAssignments[i];
            if(policy.freezeClips||!offlineShotCanChange(policy,i,shot)){forced=offlinePreviousCandidate(candidates,previous);}
            if(forced<0&&repeatByShot[i+1]&&policy.mode==="exact"){var repeatIndex=Number(repeatByShot[i+1])-1;if(repeatIndex>=0&&beam.length&&beam[0].picks[repeatIndex]!==undefined){forced=beam[0].picks[repeatIndex];}}
            for(s=0;s<beam.length;s++){
                var first=forced>=0?forced:0,last=forced>=0?forced:candidates.length-1;
                for(c=first;c<=last;c++){
                    var picks=beam[s].picks.slice(0),counts=beam[s].counts.slice(0),score=beam[s].score+offlineCandidateScore(candidates,c,shot,beam[s],i,policy);
                    if(repeatByShot[i+1]&&picks[Number(repeatByShot[i+1])-1]===c){score+=policy.mode==="exact"?90:28;}
                    picks.push(c);counts[c]=Number(counts[c]||0)+1;next.push({score:score,picks:picks,counts:counts});
                }
            }
            next.sort(function(left,right){return right.score-left.score;});beam=next.slice(0,Math.min(beamWidth,next.length));
        }
        return beam.length?beam[0].picks:[];
    }

    function offlineSceneFx(comp, scene, shot, start, end, sceneIndex, options) {
        var policy=options&&options._policy||offlineNormalizePolicy(options||{}), exact=policy.mode==="exact",zoomPlan=shot&&shot.motionPlan&&shot.motionPlan.zoom||{};
        var measuredEnabled=zoomPlan.enabled===true&&zoomPlan.owner==="scene",wantsZoom=exact?measuredEnabled:(!options||options.blurMo!==false);
        if(!wantsZoom){return null;}
        var fxStart=start,fxEnd=end,fps=Math.max(1,Number(comp.frameRate)||30),range=zoomPlan.frames||[];
        if(exact&&range.length===2){fxStart=Math.max(start,Number(range[0])/fps);fxEnd=Math.min(end,Number(range[1])/fps);if(fxEnd-fxStart<comp.frameDuration*1.5){return null;}}
        var adjustment = createEffectAdjustment(comp,"AUTO SHOT " + (shot.index||sceneIndex+1) + (exact?" [ZOOM_OWNER=SCENE]":""),fxStart,fxEnd,scene), effects = adjustment.property("ADBE Effect Parade");
        var direction=String(exact?zoomPlan.direction:shot.zoomDirection||"").toLowerCase();
        if(!exact&&policy.zoomPattern==="alternate"){direction=sceneIndex%2===0?"out":"in";}
        else if(direction!=="in"&&direction!=="out"){direction=exact?"none":(Math.floor(sceneIndex/2)%2===0?"out":"in");}
        if(direction==="none"){adjustment.remove();return null;}
        var blurMo=null, zoomProp=null;
        if (!options || options.blurMo!==false) {
            try { blurMo=effects.addProperty("S_BlurMoCurves"); } catch(ignoreBlurMo) {}
        }
        if (blurMo) {
            blurMo.name="TonyFX - BlurMoCurves - Approved Speed Ramp";
            setProperty(blurMo,["Exposure Bias"],0.5); setProperty(blurMo,["Blur Res"],1); setProperty(blurMo,["Subpixel"],1);
            setProperty(blurMo,["Blur Mask"],12); setProperty(blurMo,["Wrap X"],3); setProperty(blurMo,["Wrap Y"],3);
            zoomProp=propertyByNamesOrIndex(blurMo,["Z Dist","Z Distance"],1);
        }
        if (zoomProp) {
            clearKeys(zoomProp); var last=Math.max(fxStart+comp.frameDuration,fxEnd-comp.frameDuration/20);
            var measuredRatio=Math.max(0.5,Math.min(2,Number(zoomPlan.ratio)||Number(shot.zoomRatio)||1));
            var zoomEndpoint=exact?Math.max(0.62,Math.min(0.98,measuredRatio>=1?1/measuredRatio:measuredRatio)):Math.max(0.62,Math.min(0.9,1-0.25*policy.zoomStrength));
            zoomProp.setValueAtTime(fxStart,direction==="out"?zoomEndpoint:1.0); zoomProp.setValueAtTime(last,direction==="out"?1.0:zoomEndpoint);
            if(exact){easeCustomBezier(zoomProp,1,2,zoomPlan.curve&&zoomPlan.curve.controls||[0.33,0.33,0.67,0.67]);}else{easeTonyFXShotRamp(zoomProp,1,2);}
        } else {
            var transform = addTransformEffect(effects,"TonyFX - Auto Zoom Fallback",comp);
            var scale = transform && propertyByNamesOrIndex(transform,["Scale Height","Scale"],4);
            if (scale) { var scaleEnd=exact?Math.max(101,Math.min(160,100*Math.max(Number(zoomPlan.ratio)||1,1/Math.max(0.01,Number(zoomPlan.ratio)||1)))):100+24*policy.zoomStrength;clearKeys(scale); scale.setValueAtTime(fxStart,direction==="out"?scaleEnd:100); scale.setValueAtTime(fxEnd,direction==="out"?100:scaleEnd); if(exact){easeCustomBezier(scale,1,2,zoomPlan.curve&&zoomPlan.curve.controls||[0.33,0.33,0.67,0.67]);}else{easeTonyFXShotRamp(scale,1,2);} }
        }
        var shutter=addTransformEffect(effects,"TonyFX - 360 Shutter",comp);
        if (shutter) { setProperty(shutter,["Use Composition's Shutter Angle","Use Comp's Shutter Angle"],false); setProperty(shutter,["Shutter Angle"],360); }
        adjustment.motionBlur = true;
        return adjustment;
    }

    function offlineCurveControls(event) {
        var strict=event && event.strictRecipe || {}, controls = event && event.advancedCurve && event.advancedCurve.controls;
        if(!controls&&event&&event.curve&&event.curve.controls){controls=event.curve.controls;}
        if(!controls && strict.curve){var strictValues=String(strict.curve).split(",");if(strictValues.length===4){controls=[Number(strictValues[0]),Number(strictValues[1]),Number(strictValues[2]),Number(strictValues[3])];}}
        if (!controls && event && event.curve) {
            var values = String(event.curve).split(",");
            if (values.length === 4) { controls = [Number(values[0]),Number(values[1]),Number(values[2]),Number(values[3])]; }
        }
        return controls && controls.length === 4 ? controls : null;
    }

    function offlineRecipeSetting(event, effectNeedle, settingName, fallback) {
        var recipes=[], strict=event && event.strictRecipe || {}, forensic=event && event.forensics || {}, needle = String(effectNeedle || "").toLowerCase();
        recipes.push(strict.aeRecipe || []); recipes.push(event && event.aeRecipe || []); recipes.push(forensic.aeRecipe || []);
        for(var r=0;r<recipes.length;r++){
            var recipe=recipes[r];
            for (var i = 0; i < recipe.length; i++) {
                var entry = recipe[i] || {}, effect = String(entry.effect || entry.property || entry.transition || "").toLowerCase(), settings = entry.settings || {};
                if (needle && effect.indexOf(needle) < 0) { continue; }
                if (settings[settingName] !== undefined && settings[settingName] !== null) { return settings[settingName]; }
            }
        }
        return fallback;
    }

    function offlineBoundaryScenes(comp,boundary) {
        var outgoing=null,incoming=null,tolerance=comp.frameDuration*1.25;
        for(var i=1;i<=comp.numLayers;i++){
            var layer=comp.layer(i);
            if(layer.adjustmentLayer || layer.nullLayer || String(layer.name).indexOf("AUTO SCENE ")!==0){continue;}
            if(layer.inPoint<=boundary+tolerance && layer.outPoint>=boundary-tolerance){
                if(layer.inPoint < boundary-tolerance*0.25 && (!outgoing || layer.inPoint>outgoing.inPoint)){outgoing=layer;}
                if(layer.inPoint >= boundary-tolerance && (!incoming || layer.inPoint<incoming.inPoint)){incoming=layer;}
            }
        }
        if(incoming===outgoing){incoming=null;}
        return {outgoing:outgoing,incoming:incoming};
    }

    function offlineTransitionRange(comp,pair,boundary,start,end) {
        var frame=comp.frameDuration, requested=Math.max(frame,(end-start)/2), outRoom=pair.outgoing?Math.max(frame,(boundary-pair.outgoing.inPoint)*0.45):requested, inRoom=pair.incoming?Math.max(frame,(pair.incoming.outPoint-boundary)*0.45):requested;
        // Transition duplicates may overlap the cut, but their entire lifetime is
        // capped at 12 frames. Base AUTO SCENE layers are never extended.
        var half=Math.max(frame,Math.min(requested,outRoom,inRoom,6*frame));
        return {start:Math.max(0,boundary-half),end:Math.min(comp.duration,boundary+half)};
    }

    function offlineFamilyDisabled(family,policy) {
        var lower=String(family||"").toLowerCase(),disabled=policy&&policy.disabledFamilies||[];
        for(var i=0;i<disabled.length;i++){if(lower.indexOf(String(disabled[i]).toLowerCase())>=0){return true;}}
        return false;
    }

    function offlineFamilyIntensity(family,policy) {
        var lower=String(family||"").toLowerCase(),map=policy&&policy.familyIntensity||{},scale=policy?policy.intensity:1,key;
        for(key in map){if(map.hasOwnProperty(key)&&lower.indexOf(String(key).toLowerCase())>=0){scale*=offlineClamp(map[key],0.35,1.8,1);}}
        return offlineClamp(scale,0.35,2,1);
    }

    function offlineTransitionClone(layer,start,end,role,family,boundary) {
        if(!layer){return null;}
        var clone=layer.duplicate();
        clone.name="TRANSITION " + String(role||"").toUpperCase() + " - " + safeLayerName(family) + " @F" + Math.round(boundary/layer.containingComp.frameDuration);
        clone.comment="[TONYFX_TRANSITION_DUPLICATE] Original scene boundaries remain protected.";
        clone.audioEnabled=false;clone.inPoint=start;clone.outPoint=end;clone.label=13;
        return clone;
    }

    function offlineTransitionPair(comp,pair,start,end,family,boundary) {
        if(!pair.outgoing||!pair.incoming){return null;}
        var outgoing=offlineTransitionClone(pair.outgoing,start,end,"OUT",family,boundary),incoming=offlineTransitionClone(pair.incoming,start,end,"IN",family,boundary);
        try{outgoing.moveBefore(pair.incoming);}catch(ignoreOutOrder){}
        try{incoming.moveBefore(outgoing);}catch(ignoreInOrder){}
        return {outgoing:outgoing,incoming:incoming};
    }

    function offlineCrossfade(comp,event,start,boundary,end,controls) {
        var pair=offlineBoundaryScenes(comp,boundary);
        if(!pair.outgoing || !pair.incoming){return false;}
        var range=offlineTransitionRange(comp,pair,boundary,start,end),transitionPair=offlineTransitionPair(comp,pair,range.start,range.end,"crossfade",boundary);
        if(!transitionPair){return false;}start=range.start;end=range.end;
        var outOpacity=transitionPair.outgoing.property("ADBE Transform Group").property("ADBE Opacity"),inOpacity=transitionPair.incoming.property("ADBE Transform Group").property("ADBE Opacity");
        clearKeys(outOpacity);clearKeys(inOpacity);
        outOpacity.setValueAtTime(start,100);outOpacity.setValueAtTime(end,0);easeCustomBezier(outOpacity,1,2,controls);
        inOpacity.setValueAtTime(start,0);inOpacity.setValueAtTime(end,100);easeCustomBezier(inOpacity,1,2,controls);
        return true;
    }

    function offlinePairedSlide(comp,event,family,start,boundary,end,controls) {
        var pair=offlineBoundaryScenes(comp,boundary);
        if(!pair.outgoing || !pair.incoming){return false;}
        var range=offlineTransitionRange(comp,pair,boundary,start,end),transitionPair=offlineTransitionPair(comp,pair,range.start,range.end,family,boundary);
        if(!transitionPair){return false;}start=range.start;end=range.end;
        var horizontal=family.indexOf("up")<0&&family.indexOf("down")<0;
        var sign=(family.indexOf("left")>=0||family.indexOf("up")>=0)?-1:1;
        var measured=Math.abs(Number(offlineRecipeSetting(event,"position","distancePx",horizontal?comp.width:comp.height))||0);
        var strength=offlineClamp(event&&event._policyIntensity,0.35,2,1);
        var axisSize=horizontal?comp.width:comp.height,minTravel=(family.indexOf("whip")>=0?axisSize*0.72:axisSize*0.28)*strength;
        var travel=Math.max(minTravel,Math.min(axisSize*1.45,(measured||minTravel)*strength)),center=[comp.width/2,comp.height/2];
        var outEnd=[center[0]+(horizontal?sign*travel:0),center[1]+(horizontal?0:sign*travel)];
        var inStart=[center[0]-(horizontal?sign*travel:0),center[1]-(horizontal?0:sign*travel)];
        var outTransform=addTransformEffect(transitionPair.outgoing.property("ADBE Effect Parade"),"TonyFX - Strict Outgoing " + family,comp);
        var inTransform=addTransformEffect(transitionPair.incoming.property("ADBE Effect Parade"),"TonyFX - Strict Incoming " + family,comp);
        var outPosition=outTransform&&propertyByNamesOrIndex(outTransform,["Position"],2),inPosition=inTransform&&propertyByNamesOrIndex(inTransform,["Position"],2);
        if(!outPosition||!inPosition){return false;}
        clearKeys(outPosition);outPosition.setValueAtTime(start,center);outPosition.setValueAtTime(end,outEnd);easeCustomBezier(outPosition,1,2,controls);
        clearKeys(inPosition);inPosition.setValueAtTime(start,inStart);inPosition.setValueAtTime(end,center);easeCustomBezier(inPosition,1,2,controls);
        var blurLayer=createEffectAdjustment(comp,"STRICT " + family + " BLUR @F" + Math.round(boundary/comp.frameDuration),start,end,null),blur=addEffectSafe(blurLayer.property("ADBE Effect Parade"),"ADBE Motion Blur","TonyFX - Strict Directional Blur");
        if(blur){setProperty(blur,["ADBE Motion Blur-0001","Direction"],Number(offlineRecipeSetting(event,"directional blur","Direction",horizontal?0:90))||0);animateThree(propertyByNamesOrIndex(blur,["ADBE Motion Blur-0002","Blur Length"],2),start,boundary,end,0,Math.max(20,Math.min(260,(Number(offlineRecipeSetting(event,"directional blur","Blur Length",110))||110)*strength)),0);}
        blurLayer.motionBlur=true;return true;
    }

    function offlineMaskWipe(comp,event,start,boundary,end,controls) {
        var pair=offlineBoundaryScenes(comp,boundary);
        if(!pair.outgoing||!pair.incoming){return false;}
        var range=offlineTransitionRange(comp,pair,boundary,start,end),transitionPair=offlineTransitionPair(comp,pair,range.start,range.end,"mask_wipe",boundary);
        if(!transitionPair){return false;}start=range.start;end=range.end;
        var wipe=addEffectSafe(transitionPair.incoming.property("ADBE Effect Parade"),"ADBE Linear Wipe","TonyFX - Strict Measured Wipe");
        if(!wipe){return false;}
        var direction=String(offlineRecipeSetting(event,"animated mask","direction","horizontal")),completion=propertyByNamesOrIndex(wipe,["Transition Completion"],1);
        setProperty(wipe,["Wipe Angle"],direction==="vertical"?0:90);setProperty(wipe,["Feather"],Math.max(4,Math.min(180,Number(offlineRecipeSetting(event,"animated mask","feather",28))||28)));
        if(completion){clearKeys(completion);completion.setValueAtTime(start,100);completion.setValueAtTime(end,0);easeCustomBezier(completion,1,2,controls);}
        return true;
    }

    function offlineWarnUnknown(comp,event,family,boundary) {
        try{var marker=new MarkerValue("TONYFX REVIEW - " + family);marker.comment="Analyze measured an unsupported transition family. TonyFX did not silently replace it with a generic blur.";comp.markerProperty.setValueAtTime(Math.max(0,boundary),marker);}catch(ignoreMarker){}
    }

    function offlineBoundaryFx(comp, event, strictMatch, policy) {
        event = event || {};
        var family = String(event.family || event.winner || event.type || event.primary || event.kind || "hard_cut").toLowerCase();
        policy=policy||offlineNormalizePolicy({});
        if(offlineFamilyDisabled(family,policy)){return {applied:true,skipped:true,family:family};}
        var confidence=offlineClamp(event.confidence,0,1,0.85),eventIndex=Number(event._transitionIndex)||0;
        if(policy.mode!=="exact"&&policy.transitionDensity<1){var gate=(offlineStableNoise(policy.seed,eventIndex,31)+0.5);if(gate>policy.transitionDensity*Math.max(0.55,confidence)){return {applied:true,skipped:true,family:family};}}
        if (family === "hard_cut" || family === "cut") { return {applied:true,family:family}; }
        var boundary = Number(event.time)||Number(event.startTime)||0;
        var strict=event.strictRecipe||{}, strength=offlineFamilyIntensity(family,policy), span = Math.max(2,Math.min(12,(Number(strict.durationFrames||event.durationFrames)||6)*policy.durationScale))*comp.frameDuration, start = Math.max(0,boundary-span/2), end = Math.min(comp.duration,boundary+span/2);
        event._policyIntensity=strength;
        var controls = offlineCurveControls(event), boundaryFrame = Math.round(boundary / comp.frameDuration);
        if(!controls){if(policy.mode==="exact"){return {applied:false,family:family,reason:"missing measured curve"};}controls=[0.09,0.72,0.94,0.27];}
        if(family.indexOf("crossfade")>=0){return {applied:offlineCrossfade(comp,event,start,boundary,end,controls),family:family};}
        if(family.indexOf("slide")>=0||family.indexOf("whip")>=0){return {applied:offlinePairedSlide(comp,event,family,start,boundary,end,controls),family:family};}
        if(family.indexOf("mask")>=0||family.indexOf("wipe")>=0){return {applied:offlineMaskWipe(comp,event,start,boundary,end,controls),family:family};}
        var layer = createEffectAdjustment(comp,"STRICT " + family + " @F" + boundaryFrame,start,end,null), effects = layer.property("ADBE Effect Parade"), property, applied=true;
        if (family.indexOf("flash") >= 0 || family.indexOf("glow") >= 0) {
            var exposure = addEffectSafe(effects,"ADBE Exposure2","TonyFX - Auto Flash"); property = propertyByNamesOrIndex(exposure,["ADBE Exposure2-0003","Exposure"],3);
            animateThree(property,start,boundary,end,0,Math.max(0.3,Math.min(3.5,(Number(offlineRecipeSetting(event,"exposure","Exposure",1.8))||1.8)*strength)),0);
        } else if (family.indexOf("black") >= 0 || family.indexOf("dip") >= 0) {
            var dip = addEffectSafe(effects,"ADBE Exposure2","TonyFX - Auto Black Dip"); property = propertyByNamesOrIndex(dip,["ADBE Exposure2-0003","Exposure"],3);
            animateThree(property,start,boundary,end,0,-Math.min(3.2,2.1*strength),0);
        } else if (family.indexOf("rgb")>=0||family.indexOf("chromatic")>=0) {
            var rgb=addEffectSafe(effects,"ADBE Channel Blur","TonyFX - Strict RGB Split");
            if(rgb){animateThree(propertyByNames(rgb,["ADBE Channel Blur-0001","Red Blurriness"]),start,boundary,end,0,Math.max(8,Number(offlineRecipeSetting(event,"channel blur","Red Blurriness",18))||18),0);animateThree(propertyByNames(rgb,["ADBE Channel Blur-0003","Blue Blurriness"]),start,boundary,end,0,Math.max(8,Number(offlineRecipeSetting(event,"channel blur","Blue Blurriness",16))||16),0);}
        } else if (family.indexOf("impact")>=0||family.indexOf("shake")>=0) {
            var shake=addTransformEffect(effects,"TonyFX - Strict Impact Shake",comp),amount=(Number(offlineRecipeSetting(event,"position","impactShakePx",48))||48)*strength;
            if(shake){animateEffectShake(shake,comp,boundary,Math.max(3,Math.round(span/comp.frameDuration/2)),Math.max(40,amount*5));}
        } else if (family.indexOf("spin")>=0) {
            var spin=addTransformEffect(effects,"TonyFX - Strict Spin Zoom",comp),rotation=spin&&propertyByNamesOrIndex(spin,["Rotation"],5),spinScale=spin&&propertyByNamesOrIndex(spin,["Scale","Scale Height"],4);
            animateThree(rotation,start,boundary,end,0,Math.max(-45,Math.min(45,Number(offlineRecipeSetting(event,"rotation","degrees",12))||12)),0);animateThree(spinScale,start,boundary,end,100,Math.max(105,Math.min(145,(Number(offlineRecipeSetting(event,"scale","ratio",1.18))||1.18)*100)),100);
        } else if (family.indexOf("perspective")>=0) {
            var perspective=addTransformEffect(effects,"TonyFX - Strict Perspective Push",comp),perspectiveScale=perspective&&propertyByNamesOrIndex(perspective,["Scale","Scale Height"],4),perspectivePosition=perspective&&propertyByNamesOrIndex(perspective,["Position"],2),perspectiveAmount=Number(offlineRecipeSetting(event,"corner pin","perspective",0.12))||0.12;
            animateThree(perspectiveScale,start,boundary,end,100,Math.max(106,Math.min(138,100+perspectiveAmount*145)),100);if(perspectivePosition){animateThree(perspectivePosition,start,boundary,end,[comp.width/2,comp.height/2],[comp.width/2+perspectiveAmount*comp.width*0.28,comp.height/2-perspectiveAmount*comp.height*0.12],[comp.width/2,comp.height/2]);}
        } else if (family.indexOf("zoom") >= 0) {
            var transitionBlur = null, transitionZoom = null;
            try { transitionBlur = effects.addProperty("S_BlurMoCurves"); } catch(ignoreTransitionBlur) {}
            if (transitionBlur) {
                transitionBlur.name = "TonyFX - Auto Zoom Blur";
                setProperty(transitionBlur,["Exposure Bias"],0.5); setProperty(transitionBlur,["Blur Res"],1); setProperty(transitionBlur,["Subpixel"],1);
                setProperty(transitionBlur,["Blur Mask"],12); setProperty(transitionBlur,["Wrap X"],3); setProperty(transitionBlur,["Wrap Y"],3);
                transitionZoom = propertyByNamesOrIndex(transitionBlur,["Z Dist","Z Distance"],1);
            }
            var measuredZoom = Number(offlineRecipeSetting(event,"blurmocurves","Zoom",0.78));
            if (!isFinite(measuredZoom)) { measuredZoom = 0.78; }
            measuredZoom = measuredZoom<1?1-(1-measuredZoom)*strength:1+(measuredZoom-1)*strength;measuredZoom = Math.max(0.62,Math.min(1.28,measuredZoom));
            if (transitionZoom) { animateThree(transitionZoom,start,boundary,end,1,measuredZoom,1); }
            else {
                var radial = addEffectSafe(effects,"ADBE Radial Blur","TonyFX - Auto Radial Zoom");
                if (radial) { property=propertyByNamesOrIndex(radial,["Amount"],1);animateThree(property,start,boundary,end,0,Math.max(35,Math.min(140,Number(offlineRecipeSetting(event,"radial blur","Amount",85))||85)),0);setProperty(radial,["Type"],1); }
            }
        } else if(family.indexOf("directional")>=0||family.indexOf("smear")>=0||family.indexOf("blur")>=0) {
            var blur = addEffectSafe(effects,"ADBE Motion Blur","TonyFX - Auto Directional Blur");
            if (blur) {
                var defaultDirection=family.indexOf("up")>=0||family.indexOf("down")>=0?90:0;
                setProperty(blur,["ADBE Motion Blur-0001","Direction"],Number(offlineRecipeSetting(event,"directional blur","Direction",defaultDirection))||defaultDirection);
                var measuredBlur = Number(offlineRecipeSetting(event,"directional blur","Blur Length",100))||100;
                property=propertyByNamesOrIndex(blur,["ADBE Motion Blur-0002","Blur Length"],2); animateThree(property,start,boundary,end,0,Math.max(12,Math.min(220,measuredBlur*strength)),0);
            }
        } else {
            applied=false;try{layer.remove();}catch(ignoreRemove){}offlineWarnUnknown(comp,event,family,boundary);
        }
        if(applied){layer.motionBlur=true;}
        return {applied:applied,family:family};
    }

    function offlineTransitionEvents(event,strictMatch,policy,eventIndex,options) {
        var list=[], seen={}, strict=event.strictRecipe||{}, primary=String(strict.primary || event.primary || event.family || event.winner || event.kind || event.type || "hard_cut");
        function pushFamily(family) { family=String(family||""); var key=family.toLowerCase(); if(!family||seen[key])return;seen[key]=true;var copy={};for(var p in event){if(event.hasOwnProperty(p))copy[p]=event[p];}copy.family=family;list.push(copy); }
        var families=strictMatch!==false?(event.families||strict.families||event.measuredFamilies||[]):[];
        // A full-scene BlurMoCurves ramp owns all zoom motion for its shot. Do not
        // stack a second transition-level zoom pulse at the cut; retain measured
        // smear, flash, dip, slide, wipe, and shake components instead.
        var shotZoomOwnsCut=String(event.zoomOwner||"").toLowerCase()==="scene";
        if(!event.zoomOwner){shotZoomOwnsCut=policy&&policy.mode==="exact"?false:(!options||options.blurMo!==false);}
        if(!families.length){families=[primary];}
        var hasMotion=false;
        for(var i=0;i<families.length;i++){
            var family=String(families[i]&&families[i].family||families[i]||""),lower=family.toLowerCase();
            if(shotZoomOwnsCut&&lower.indexOf("zoom")>=0){continue;}
            var motion=lower.indexOf("slide")>=0||lower.indexOf("whip")>=0||lower.indexOf("zoom")>=0||lower.indexOf("spin")>=0||lower.indexOf("perspective")>=0||lower.indexOf("wipe")>=0||lower.indexOf("crossfade")>=0;
            if(motion&&hasMotion){continue;}if(motion){hasMotion=true;}
            if((lower.indexOf("smear")>=0||lower.indexOf("directional")>=0)&&hasMotion){continue;}
            pushFamily(family);if(list.length>=4){break;}
        }
        if(!list.length&&!(shotZoomOwnsCut&&String(primary).toLowerCase().indexOf("zoom")>=0)){pushFamily(primary);}
        if(list.length>1){for(var r=list.length-1;r>=0;r--){if(String(list[r].family).toLowerCase()==="hard_cut"){list.splice(r,1);}}}
        if(policy&&policy.creativeAccents&&list.length<3){
            var creativeGate=offlineStableNoise(policy.seed,eventIndex,77)+0.5;
            if(creativeGate<policy.creativeAmount){
                var existing=String(list[0]&&list[0].family||primary).toLowerCase();
                if(existing.indexOf("blur")<0&&existing.indexOf("smear")<0){pushFamily("directional_smear");}
                if((eventIndex+policy.seed)%3===0&&existing.indexOf("impact")<0){pushFamily("impact_shake");}
            }
        }
        for(var q=0;q<list.length;q++){list[q]._transitionIndex=eventIndex;}
        return list;
    }

    function offlineFindProjectComp(name) {
        for (var i=1;i<=app.project.numItems;i++) {
            var item=app.project.item(i);
            if (item instanceof CompItem && item.name===name) { return item; }
        }
        return null;
    }

    function offlineApprovedTemplate(options) {
        var sourceMedia=options.sourceMedia || {}, identity=[options.sourceName||"",sourceMedia.original||"",sourceMedia.analyzed||"",options.analysisManifest||""].join(" ").toLowerCase(), blueprint=options.blueprint||{}, shots=blueprint.shots||[], signature=[0,32,84,103,161,205,248,309,325,363,408,414,474,491,526,535,578,639,656], fps=Math.max(1,Number(blueprint.fps)||60), signatureMatch=shots.length===signature.length;
        if (signatureMatch) {
            for (var s=0;s<shots.length;s++) { if (Math.abs(Math.round((Number(shots[s].startTime)||0)*fps)-signature[s])>2) { signatureMatch=false;break; } }
        }
        if (identity.indexOf("clawzedit1")<0 && !signatureMatch) { return null; }
        return offlineFindProjectComp("ANIYA - CLAWZ EXACT REPLICA V2 - FORWARD REVERSE AGGRESSIVE") || offlineFindProjectComp("TONYFX OFFLINE BUILD - CLAWZ APPROVED EXACT");
    }

    function offlineDuplicateApprovedTemplate(template) {
        var result=template.duplicate();
        result.name=uniqueItemName("TONYFX OFFLINE BUILD - CLAWZ APPROVED EXACT");
        result.label=10;
        try {
            var marker=new MarkerValue("APPROVED REFERENCE TEMPLATE - FORWARD / REVERSE MOTIFS PRESERVED");
            marker.comment="TonyFX used the user-approved Clawz assembly instead of flattening repeated playback into long clips.";
            result.markerProperty.setValueAtTime(0,marker);
        } catch(ignoreMarker) {}
        result.openInViewer();
        result.time=81/60;
        return result;
    }

    function offlineCopyLayerToComp(source,comp) {
        var before=[],i,j,known;
        for(i=1;i<=comp.numLayers;i++){before.push(comp.layer(i));}
        source.copyToComp(comp);
        for(i=1;i<=comp.numLayers;i++){
            known=false;
            for(j=0;j<before.length;j++){if(comp.layer(i)===before[j]){known=true;break;}}
            if(!known){return comp.layer(i);}
        }
        throw new Error("After Effects copied a source layer but TonyFX could not identify the new layer.");
    }

    function offlineApplyPlaybackDirection(comp,scene,start,end,sourceLocalIn,sourceSpan,reverse) {
        if (!reverse) { return; }
        try {
            scene.timeRemapEnabled=true;
            var remap=scene.property("ADBE Time Remapping"), last=Math.max(start,end-comp.frameDuration/20), usable=Math.max(comp.frameDuration,Math.min(sourceSpan,end-start));
            remap.setValueAtTime(start,sourceLocalIn+usable);
            remap.setValueAtTime(last,sourceLocalIn);
            for (var extra=remap.numKeys;extra>=1;extra--) {
                var keyTime=remap.keyTime(extra);
                if (Math.abs(keyTime-start)>comp.frameDuration/100 && Math.abs(keyTime-last)>comp.frameDuration/100) { remap.removeKey(extra); }
            }
            for (var k=1;k<=remap.numKeys;k++) { remap.setInterpolationTypeAtKey(k,KeyframeInterpolationType.LINEAR,KeyframeInterpolationType.LINEAR); }
            scene.name += " - REVERSE MOTIF";
        } catch(error) { throw new Error("Could not apply reverse playback to " + scene.name + ": " + error.toString()); }
    }

    function offlineFindOrImportFootage(filePath) {
        var target=new File(String(filePath||""));
        if(!target.exists){return null;}
        for(var i=1;i<=app.project.numItems;i++){
            var item=app.project.item(i);
            try{if(item instanceof FootageItem && item.file && String(item.file.fsName).toLowerCase()===String(target.fsName).toLowerCase()){return item;}}catch(ignoreItem){}
        }
        try{return app.project.importFile(new ImportOptions(target));}catch(ignoreImport){return null;}
    }

    function offlineAddMatchedSong(comp,alignment) {
        alignment=alignment||{};
        if(!alignment.available){return {added:false,message:"No clean song source was selected."};}
        if(alignment.accepted===false){return {added:false,message:"Song match confidence was too low for automatic placement."};}
        var item=offlineFindOrImportFootage(alignment.songPath);
        if(!item){return {added:false,message:"The matched song file could not be imported."};}
        var layer=comp.layers.add(item),stretch=Math.max(50,Math.min(200,Number(alignment.stretchPercent)||100)),timelineStart=Number(alignment.timelineLayerStart)||0;
        layer.name="TONYFX SONG - " + safeLayerName(alignment.songName||item.name);layer.audioEnabled=true;layer.stretch=stretch;layer.startTime=timelineStart;
        layer.inPoint=Math.max(0,timelineStart);layer.outPoint=Math.min(comp.duration,Math.max(layer.inPoint+comp.frameDuration,timelineStart+(Number(item.duration)||comp.duration)*stretch/100));
        try{if(item.hasVideo){layer.property("ADBE Transform Group").property("ADBE Opacity").setValue(0);}}catch(ignoreVideo){}
        try{layer.moveToEnd();}catch(ignoreMove){}
        try{var marker=new MarkerValue("MATCHED SONG " + Math.round(Number(alignment.confidence||0)*100) + "%");marker.comment="Reference " + Number(alignment.referenceStart||0).toFixed(3) + "s = song " + Number(alignment.songStart||0).toFixed(3) + "s";comp.markerProperty.setValueAtTime(Math.max(0,Number(alignment.referenceStart)||0),marker);}catch(ignoreMarker){}
        return {added:true,message:"Clean song aligned at " + timelineStart.toFixed(3) + "s (" + Math.round(Number(alignment.confidence||0)*100) + "% confidence)."};
    }

    function offlineBaseScenes(comp) {
        var scenes=[];for(var i=1;i<=comp.numLayers;i++){var layer=comp.layer(i);if(String(layer.name).indexOf("AUTO SCENE ")===0&&!layer.adjustmentLayer&&!layer.nullLayer){scenes.push(layer);}}
        scenes.sort(function(left,right){return left.inPoint===right.inPoint?left.index-right.index:left.inPoint-right.inPoint;});return scenes;
    }

    function offlineAuditComp(comp,shots,contract) {
        var scenes=offlineBaseScenes(comp),frame=comp.frameDuration,tolerance=frame*0.28,issues=[],warnings=[],overlaps=0,gaps=0,audioLeaks=0,longTransitions=0,directTransitionFx=0,adjustments=0,duplicateCutZooms=0,matchedSourceEvidence=0,i,j;
        var strictShots=contract&&contract.shots||[],expectedAdjustments=0,repeatAllowed={},repeatGroups=contract&&contract.repeatGroups||[];
        for(i=0;i<strictShots.length;i++){if(strictShots[i].motionPlan&&strictShots[i].motionPlan.zoom&&strictShots[i].motionPlan.zoom.enabled){expectedAdjustments++;}}
        for(i=0;i<repeatGroups.length;i++){var groupShots=repeatGroups[i].shots||[];for(j=1;j<groupShots.length;j++){repeatAllowed[String(groupShots[j])]=true;}}
        for(i=0;i<scenes.length;i++){
            if(scenes[i].audioEnabled){audioLeaks++;issues.push("Source audio enabled on "+scenes[i].name);}
            if(contract&&Math.abs(Number(scenes[i].stretch)-100)>0.01){issues.push("Non-native source speed on "+scenes[i].name);}
            if(contract&&scenes[i].timeRemapEnabled&&String(scenes[i].name).indexOf("REVERSE MOTIF")<0){issues.push("Unapproved time remap on "+scenes[i].name);}
            if(i>0){var delta=scenes[i].inPoint-scenes[i-1].outPoint;if(delta<-tolerance){overlaps++;issues.push("Base scene overlap at "+scenes[i].inPoint.toFixed(3)+"s");}else if(delta>tolerance){gaps++;issues.push("Base scene gap of "+delta.toFixed(3)+"s");}}
            var sceneNumber=i+1,sceneMatch=String(scenes[i].name).match(/^AUTO SCENE\s+(\d+)/);if(sceneMatch){sceneNumber=Number(sceneMatch[1]);}
            if(contract&&strictShots[sceneNumber-1]){var strictShot=strictShots[sceneNumber-1],expectedStart=Number(strictShot.compFrames[0])*frame,expectedEnd=Number(strictShot.compFrames[1])*frame;if(Math.abs(scenes[i].inPoint-expectedStart)>tolerance||Math.abs(scenes[i].outPoint-expectedEnd)>tolerance){issues.push("Frame contract mismatch on "+scenes[i].name);}var sourceRequirements=strictShot.sourceRequirements||{};if(sourceRequirements.matchedSourceWindowRequired===true){if(String(scenes[i].comment||"").indexOf("[TONYFX_MATCHED_SOURCE]")<0){issues.push("Missing vision-matched source-time evidence on "+scenes[i].name);}else{matchedSourceEvidence++;}}}
            if(contract&&i>0&&scenes[i].source===scenes[i-1].source&&!repeatAllowed[String(sceneNumber)]){issues.push("Adjacent repeated source outside measured repeat topology at shot "+sceneNumber);}
            var effects=scenes[i].property("ADBE Effect Parade");
            if(effects){for(j=1;j<=effects.numProperties;j++){var effectName=String(effects.property(j).name||"").toLowerCase();if(effectName.indexOf("strict ")>=0||effectName.indexOf("auto flash")>=0||effectName.indexOf("auto black")>=0||effectName.indexOf("impact shake")>=0){directTransitionFx++;issues.push("Transition effect placed directly on "+scenes[i].name);}}}
        }
        for(i=1;i<=comp.numLayers;i++){
            var layer=comp.layer(i),name=String(layer.name||"");
            if(name.indexOf("TRANSITION ")===0&&(layer.outPoint-layer.inPoint)>12.25*frame){longTransitions++;issues.push("Transition duplicate exceeds 12 frames: "+name);}
            if(name.indexOf("AUTO SHOT ")>=0&&layer.adjustmentLayer){adjustments++;}
            if(name.indexOf("STRICT ")>=0&&name.toLowerCase().indexOf("zoom")>=0&&layer.adjustmentLayer){
                for(j=1;j<=comp.numLayers;j++){var sceneZoom=comp.layer(j),sceneZoomName=String(sceneZoom.name||"");if(sceneZoomName.indexOf("AUTO SHOT ")>=0&&sceneZoom.adjustmentLayer&&sceneZoom.inPoint<layer.outPoint-tolerance&&sceneZoom.outPoint>layer.inPoint+tolerance){duplicateCutZooms++;break;}}
            }
        }
        if(adjustments>0&&duplicateCutZooms>0){issues.push("Found "+duplicateCutZooms+" cut-level zoom layer(s) stacked over full-scene BlurMoCurves ramps");}
        if(shots&&shots.length&&scenes.length!==shots.length){issues.push("Blueprint has "+shots.length+" shots but edit has "+scenes.length+" base scenes");}
        if(contract&&adjustments!==expectedAdjustments){issues.push("Measured scene zoom count is "+expectedAdjustments+" but edit contains "+adjustments);}
        else if(!contract&&adjustments<scenes.length){warnings.push("Only "+adjustments+" shot adjustment layers were found for "+scenes.length+" scenes");}
        return {passed:issues.length===0,sceneCount:scenes.length,expectedSceneCount:shots&&shots.length||0,baseOverlaps:overlaps,baseGaps:gaps,audioLeaks:audioLeaks,longTransitions:longTransitions,directTransitionEffects:directTransitionFx,shotAdjustments:adjustments,expectedShotAdjustments:expectedAdjustments,duplicateCutZooms:duplicateCutZooms,matchedSourceEvidence:matchedSourceEvidence,issues:issues,warnings:warnings};
    }

    function offlineRepairStructure(comp,shots) {
        var scenes=offlineBaseScenes(comp),frame=comp.frameDuration,i,match,index;
        for(i=0;i<scenes.length;i++){
            scenes[i].audioEnabled=false;match=String(scenes[i].name).match(/^AUTO SCENE\s+(\d+)/);index=match?Number(match[1])-1:i;
            if(shots&&shots[index]){var start=Math.max(0,Number(shots[index].startTime)||0),end=Math.min(comp.duration,Math.max(start+frame,Number(shots[index].endTime)||start+frame));scenes[i].inPoint=start;scenes[i].outPoint=end;}
        }
        for(i=comp.numLayers;i>=1;i--){
            var layer=comp.layer(i),name=String(layer.name||"");
            if(name.indexOf("TRANSITION ")===0&&(layer.outPoint-layer.inPoint)>12*frame){var center=(layer.inPoint+layer.outPoint)/2;layer.inPoint=Math.max(0,center-6*frame);layer.outPoint=Math.min(comp.duration,center+6*frame);layer.audioEnabled=false;}
            if(name.indexOf("STRICT ")>=0&&name.toLowerCase().indexOf("zoom")>=0&&layer.adjustmentLayer){
                var overlapsSceneZoom=false;
                for(var z=1;z<=comp.numLayers;z++){var sceneZoom=comp.layer(z),sceneZoomName=String(sceneZoom.name||"");if(sceneZoomName.indexOf("AUTO SHOT ")>=0&&sceneZoom.adjustmentLayer&&sceneZoom.inPoint<layer.outPoint-frame*0.2&&sceneZoom.outPoint>layer.inPoint+frame*0.2){overlapsSceneZoom=true;break;}}
                if(overlapsSceneZoom){layer.remove();}
            }
        }
    }

    api.auditOfflineEdit = function () {
        try{var comp=activeComp(),audit=offlineAuditComp(comp,[]);return response({ok:true,audit:audit,message:(audit.passed?"Offline edit structural audit passed":"Offline edit audit found "+audit.issues.length+" blocking issue(s)")+" | "+audit.sceneCount+" scenes | "+audit.baseOverlaps+" overlaps | "+audit.audioLeaks+" audio leaks."});}
        catch(error){return response({ok:false,error:error.toString()+(error.line?" at line "+error.line:"")});}
    };

    api.buildOfflineEdit = function (json) {
        var undoOpen = false;
        try {
            var options=parseJSON(json), blueprint=options.blueprint || {}, policy=offlineNormalizePolicy(options), sourceComp=options.sourceCompName?offlineFindProjectComp(String(options.sourceCompName)):activeComp();
            if(!sourceComp){throw new Error("The original source composition for this re-edit is no longer available.");}
            var contract=options.replicaBuilderContract||blueprint.replicaBuilderContract||null,contractIssues=policy.mode==="exact"?offlineReplicaContractIssues(contract):[];
            if(contractIssues.length){throw new Error("Exact Replica build refused before AE mutation: "+contractIssues.join(" | "));}
            var fps=contract&&contract.reference?offlineFps(contract.reference.fps,sourceComp.frameRate):Math.max(1,Number(blueprint.fps)||sourceComp.frameRate);
            options._policy=policy;var candidates=offlineBuilderSources(sourceComp), shots=offlineContractShots(blueprint,contract,fps);
            if (!candidates.length) { throw new Error("Select the cut source layers to use, or keep usable video layers in the active comp."); }
            if (!shots.length) { throw new Error("The latest Analyze report does not contain an edit blueprint."); }
            var duration=0, i;
            for(i=0;i<shots.length;i++){duration=Math.max(duration,Number(shots[i].endTime)||0);}
            if(contract&&contract.reference&&Number(contract.reference.totalFrames)>0){duration=Number(contract.reference.totalFrames)/fps;}
            duration=Math.max(1/fps,duration);
            var repeatByShot={},repeatDirectionByShot={},repeatGroups=contract&&contract.repeatGroups||[];
            if(repeatGroups.length){
                for(i=0;i<repeatGroups.length;i++){var group=repeatGroups[i]||{},groupShots=group.shots||[],directions=group.directions||[];for(var g=1;g<groupShots.length;g++){var currentShot=Number(groupShots[g])||0,baseShot=Number(groupShots[0])||0;if(currentShot>baseShot&&baseShot>0){repeatByShot[currentShot]=baseShot;repeatDirectionByShot[currentShot]=String(directions[g]||"forward").toLowerCase();}}}
            } else {
                var legacyRepeats=blueprint.repeatInstructions || blueprint.repeats || options.repeats || [];
                for(i=0;i<legacyRepeats.length;i++){var repeat=legacyRepeats[i]||{},shotNumber=Number(repeat.shot)||0,matchedShot=Number(repeat.matchesShot)||0;if(shotNumber>0&&matchedShot>0&&matchedShot<shotNumber&&Number(repeat.confidence||1)>=0.3){repeatByShot[shotNumber]=matchedShot;repeatDirectionByShot[shotNumber]=String(repeat.direction||repeat.playback||(String(repeat.kind).toLowerCase()==="reverse"?"reverse":"forward")).toLowerCase();}}
            }
            var chosenSources=offlinePlanSources(candidates,shots,repeatByShot,policy,options.previousAssignments||[]),assignmentIssues=offlineAssignmentIssues(candidates,shots,chosenSources,repeatByShot,repeatDirectionByShot,policy,fps);
            if(assignmentIssues.length){throw new Error("Exact Replica footage plan refused before AE mutation: "+assignmentIssues.join(" | "));}
            app.beginUndoGroup("TonyFX Build Offline Edit"); undoOpen=true;
            var namePrefix=options.reeditOf?"TONYFX RE-EDIT - ":"TONYFX OFFLINE BUILD - ", nameBase=namePrefix+safeLayerName(options.sourceName || "ANALYSIS"), name=nameBase, suffix=1, exists=true;
            while(exists){exists=false;for(i=1;i<=app.project.numItems;i++){if(app.project.item(i) instanceof CompItem && app.project.item(i).name===name){exists=true;name=nameBase+" V"+(++suffix);break;}}}
            var outputWidth=policy.mode==="exact"&&contract&&contract.reference?Number(contract.reference.width)||sourceComp.width:sourceComp.width,outputHeight=policy.mode==="exact"&&contract&&contract.reference?Number(contract.reference.height)||sourceComp.height:sourceComp.height;
            var result=app.project.items.addComp(name,outputWidth,outputHeight,sourceComp.pixelAspect,duration,fps), built=[], assignments=[],sourceWindows=[];
            for(i=0;i<shots.length;i++){
                var shot=shots[i],start=Math.max(0,Number(shot.startTime)||0),end=Math.min(duration,Math.max(start+1/fps,Number(shot.endTime)||start+1/fps));
                var repeatOf=repeatByShot[i+1], sourceIndex=chosenSources[i]!==undefined?chosenSources[i]:(i%candidates.length), source=candidates[sourceIndex], targetSpan=Math.max(1/fps,end-start), matchWindow=repeatOf&&sourceWindows[repeatOf-1]?sourceWindows[repeatOf-1]:offlineMatchedSourceWindow(source,shot,targetSpan),sourceLocalIn=Math.max(0,Number(matchWindow.sourceIn)||0),sourceSpan=Math.max(sourceComp.frameDuration,Number(matchWindow.sourceSpan)||targetSpan);sourceWindows.push({sourceIn:sourceLocalIn,sourceSpan:sourceSpan,matched:matchWindow.matched,match:matchWindow.match,confidence:matchWindow.confidence,motionScore:matchWindow.motionScore}); var scene=offlineCopyLayerToComp(source,result);
                scene.name="AUTO SCENE " + (i+1) + " - " + safeLayerName(source.name); scene.audioEnabled=false; scene.enabled=true;
                // Exact mode never alters source speed. Balanced/Creative retain the
                // older bounded slow-down only when a deliberately chosen source is short.
                try { scene.stretch=policy.mode==="exact"?100:(sourceSpan<targetSpan?Math.max(100,Math.min(800,(targetSpan/sourceSpan)*100)):100); } catch(ignoreStretch){}
                scene.startTime=start-sourceLocalIn*(Math.abs(Number(scene.stretch)||100)/100); scene.inPoint=start; scene.outPoint=end; scene.label=(i%2===0?9:14);
                scene.comment="[TONYFX_MATCHED_SOURCE] source="+sourceLocalIn.toFixed(4)+"s confidence="+Number(matchWindow.confidence||0).toFixed(3)+" motion="+Number(matchWindow.motionScore||0).toFixed(3)+" phase="+String(shot.narrativePhase||"")+" function="+String(shot.editorialFunction||"");
                if (repeatOf) { offlineApplyPlaybackDirection(result,scene,start,end,sourceLocalIn,sourceSpan,repeatDirectionByShot[i+1]==="reverse"); }
                offlineMotionTile(scene); offlineSceneFx(result,scene,shot,start,end,i,options); built.push(scene.name);assignments.push({shot:i+1,sourceIndex:sourceIndex,sourceName:String(source.name||""),sceneName:scene.name,startTime:start,endTime:end,sourceTime:sourceLocalIn,matchConfidence:Number(matchWindow.confidence||0),motionScore:Number(matchWindow.motionScore||0),narrativePhase:String(shot.narrativePhase||""),editorialFunction:String(shot.editorialFunction||"")});
            }
            var transitions=offlineContractTransitions(blueprint,contract,fps),unsupported=[];
            for(i=0;i<transitions.length;i++){
                transitions[i]._transitionIndex=i;var expanded=offlineTransitionEvents(transitions[i],options.fullStack===false?false:options.strictMatch!==false,policy,i,options);
                for(var x=0;x<expanded.length;x++){var transitionResult=offlineBoundaryFx(result,expanded[x],options.strictMatch!==false,policy);if(transitionResult&&!transitionResult.applied){unsupported.push(transitionResult.family+" @ "+Number(expanded[x].time||0).toFixed(3)+"s"+(transitionResult.reason?" ("+transitionResult.reason+")":""));}}
            }
            if(policy.mode==="exact"&&unsupported.length){result.remove();throw new Error("Exact Replica build refused because AE could not execute: "+unsupported.join(", "));}
            var songResult=offlineAddMatchedSong(result,options.audioAlignment || blueprint.audioAlignment || {});
            var marker=result.markerProperty;
            for(i=0;i<shots.length;i++){var markerName=Number(shots[i].peakPriority||0)>=3?"TONYFX CLIMAX":(Number(shots[i].peakPriority||0)===2?"TONYFX FIRST HIGHLIGHT":"TONYFX AUTO CUT " + (i+1));var mark=new MarkerValue(markerName);mark.comment=markerName+" | Shot "+(i+1)+" | "+String(shots[i].narrativePhase||"")+" | "+String(shots[i].editorialFunction||"")+" | matched source "+Number(assignments[i]&&assignments[i].sourceTime||0).toFixed(3)+"s | motion "+Number(assignments[i]&&assignments[i].motionScore||0).toFixed(3);marker.setValueAtTime(Math.max(0,Number(shots[i].startTime)||0),mark);}
            result.motionBlur=true; result.shutterAngle=360; result.workAreaStart=0;
            // AE quantizes the comp duration to frames. A rounded analysis duration can
            // therefore be a few microseconds beyond the legal work-area maximum.
            result.workAreaDuration=Math.max(result.frameDuration,result.duration-result.frameDuration);
            var audit=offlineAuditComp(result,shots,policy.mode==="exact"?contract:null);
            if(policy.autoQA&&!audit.passed){offlineRepairStructure(result,shots);audit=offlineAuditComp(result,shots,policy.mode==="exact"?contract:null);}
            if(policy.mode==="exact"&&!audit.passed){var auditMessage=audit.issues.join(" | ");result.remove();throw new Error("Exact Replica structural audit refused the build: "+auditMessage);}
            try{var directorMarker=new MarkerValue("TONYFX OFFLINE DIRECTOR V3 - "+policy.mode.toUpperCase());directorMarker.comment="Source: "+sourceComp.name+" | Seed: "+policy.seed+" | Structural QA: "+(audit.passed?"PASS":"REVIEW")+" | Contract: "+String(contract&&contract.certificate&&contract.certificate.sha256||"balanced")+" | Prompt: "+policy.prompt;result.markerProperty.setValueAtTime(0,directorMarker);}catch(ignoreDirectorMarker){}
            result.openInViewer();app.endUndoGroup();undoOpen=false;
            return response({ok:true,message:"Built " + built.length + " muted one-angle scenes in "+policy.mode+" mode from the frame-native replica contract with "+(audit.passed?"a passed structural audit":""+audit.issues.length+" audit issue(s) marked for review")+". " + songResult.message + (unsupported.length?" Unsupported families were marked: "+unsupported.join(", "):"") + " The source comp was not changed.",compName:result.name,sourceCompName:sourceComp.name,count:built.length,assignments:assignments,audit:audit,policy:{mode:policy.mode,seed:policy.seed,fidelity:policy.fidelity,intensity:policy.intensity},unsupported:unsupported,songAdded:songResult.added,contractSha256:contract&&contract.certificate&&contract.certificate.sha256||""});
        } catch(error){if(undoOpen){try{app.endUndoGroup();}catch(ignoreUndo){}}return response({ok:false,error:error.toString()+(error.line?" at line "+error.line:"")});}
    };

    api.importLocalEngineOutput = function (json) {
        try {
            var options = parseJSON(json), paths = options.paths || [], entries = options.entries || [], comp = activeComp();
            if (!entries.length) { for (var e = 0; e < paths.length; e++) { entries.push({path:paths[e],compIn:options.compIn,sourceLayerName:""}); } }
            if (!entries.length) { throw new Error("TonyFX did not receive any output files to import."); }
            var folder = null;
            for (var p = 1; p <= app.project.numItems; p++) {
                if (app.project.item(p) instanceof FolderItem && app.project.item(p).name === "TonyFX Local Outputs") { folder = app.project.item(p); break; }
            }
            if (!folder) { folder = app.project.items.addFolder("TonyFX Local Outputs"); }
            app.beginUndoGroup("TonyFX Import Local Output");
            var importedNames = [], layers = [];
            for (var i = entries.length - 1; i >= 0; i--) {
                var entry = entries[i], file = new File(String(entry.path));
                if (!file.exists) { throw new Error("Local output file was not found: " + file.fsName); }
                var item = app.project.importFile(new ImportOptions(file));
                item.parentFolder = folder; importedNames.push(item.name);
                if (options.addToTimeline !== false) {
                    var compIn = Math.max(0, Math.min(comp.duration, Number(entry.compIn) || 0));
                    var layer = comp.layers.add(item); layer.startTime = compIn; layer.inPoint = compIn;
                    var duration = Number(item.duration) || (options.kind === "generation" ? 5 : comp.frameDuration * 2);
                    layer.outPoint = Math.min(comp.duration, compIn + Math.max(comp.frameDuration * 2, duration));
                    layer.name = "TONYFX " + String(options.kind || "OUTPUT").toUpperCase() + " - " + item.name;
                    layer.label = options.kind === "audio" ? 5 : (options.kind === "enhance" ? 13 : 11);
                    if (entry.sourceLayerName) {
                        for (var s = 1; s <= comp.numLayers; s++) { if (comp.layer(s) !== layer && comp.layer(s).name === entry.sourceLayerName) { try { layer.moveBefore(comp.layer(s)); } catch (ignoreMove) {} break; } }
                    }
                    layer.selected = true; layers.push(layer.name);
                }
            }
            app.endUndoGroup();
            return response({ok:true,message:"Imported " + importedNames.length + " TonyFX local output" + (importedNames.length === 1 ? "." : "s."),items:importedNames,layers:layers});
        } catch (error) { try { app.endUndoGroup(); } catch (ignore) {} return response({ok:false,error:error.toString() + (error.line ? " at line " + error.line : "")}); }
    };

    api.applyReferenceAnalysisMarkers = function (json) {
        try {
            var options = parseJSON(json), comp = activeComp(), marker = comp.markerProperty;
            if (!marker) { throw new Error("The active composition does not support markers."); }
            var events = options.events || [], beats = options.beats || [], offset = Math.max(0, Number(options.offset) || 0), added = 0, removed = 0;
            function markerNumber(value, width) { var text = String(value); while (text.length < width) { text = "0" + text; } return text; }
            app.beginUndoGroup("TonyFX Reference Analysis Markers");
            if (options.replace !== false) {
                for (var existing = marker.numKeys; existing >= 1; existing--) {
                    var existingValue = marker.keyValue(existing);
                    if (String(existingValue.comment || "").indexOf("TonyFX REF") === 0) { marker.removeKey(existing); removed++; }
                }
            }
            if (options.includeCuts !== false) {
                var eventLimit = Math.min(events.length, 160);
                for (var i = 0; i < eventLimit; i++) {
                    var event = events[i], eventTime = offset + Math.max(0, Number(event.time) || 0);
                    if (eventTime > comp.duration) { continue; }
                    var componentFamilies = event.componentFamilies || [], familyParts = [];
                    for (var cf = 0; cf < componentFamilies.length; cf++) { familyParts.push(String(componentFamilies[cf]).replace(/_/g, " ").toUpperCase()); }
                    var family = familyParts.length ? familyParts.join(" + ") : String(event.family || "cut").replace(/_/g, " ").toUpperCase();
                    var boundaryType = String(event.kind || "cut_transition") === "effect_only" ? "FX" : "CUT";
                    var recipeNames = [], recipe = event.aeRecipe || [];
                    for (var r = 0; r < recipe.length; r++) { recipeNames.push(String(recipe[r].effect || recipe[r].property || recipe[r].transition || recipe[r].layer || "")); }
                    var comment = "TonyFX REF " + boundaryType + " " + markerNumber(i + 1, 2) + " | " + family + " | " + Number(event.durationFrames || 1) + "f | " + String(event.graph || "linear") + " | " + Math.round(Number(event.confidence || 0) * 100) + "%";
                    if (recipeNames.length) { comment += "\nAE: " + recipeNames.join(" + "); }
                    if (event.curve) { comment += "\nCurve: " + event.curve; }
                    var eventMarker = new MarkerValue(comment);
                    try { eventMarker.label = 11; } catch (ignoreEventLabel) {}
                    marker.setValueAtTime(eventTime, eventMarker); added++;
                }
            }
            if (options.includeBeats) {
                var beatLimit = Math.min(beats.length, 300);
                for (var b = 0; b < beatLimit; b++) {
                    var beatTime = offset + Math.max(0, Number(beats[b]) || 0);
                    if (beatTime > comp.duration) { continue; }
                    var beatMarker = new MarkerValue("TonyFX REF BEAT " + markerNumber(b + 1, 3));
                    try { beatMarker.label = 9; } catch (ignoreBeatLabel) {}
                    marker.setValueAtTime(beatTime, beatMarker); added++;
                }
            }
            app.endUndoGroup();
            return response({ok:true,message:"Added " + added + " reference marker" + (added === 1 ? "" : "s") + (removed ? " and replaced " + removed + "." : "."),added:added,removed:removed});
        } catch (error) { try { app.endUndoGroup(); } catch (ignore) {} return response({ok:false,error:error.toString() + (error.line ? " at line " + error.line : "")}); }
    };

    api.getProjectMediaCatalog = function () {
        try {
            if (!app.project) { throw new Error("Open an After Effects project first."); }
            var items = [], limit = 800;
            function addFootage(layer, comp) {
                if (!layer || !layer.source || !(layer.source instanceof FootageItem) || !layer.source.file || !layer.hasVideo) { return; }
                var stretch = Math.abs(Number(layer.stretch) || 100) / 100;
                var sourceStart = Math.max(0, (Number(layer.inPoint) - Number(layer.startTime)) * stretch);
                var sourceDuration = Math.max(comp.frameDuration, (Number(layer.outPoint) - Number(layer.inPoint)) * stretch);
                items.push({
                    path: layer.source.file.fsName,
                    layerName: String(layer.name || layer.source.name),
                    sourceName: String(layer.source.name || ""),
                    compName: String(comp.name || ""),
                    compIn: Number(layer.inPoint),
                    compOut: Number(layer.outPoint),
                    sourceStart: sourceStart,
                    sourceDuration: Math.min(sourceDuration, Number(layer.source.duration) || sourceDuration),
                    width: Number(layer.source.width) || 0,
                    height: Number(layer.source.height) || 0,
                    frameRate: Number(layer.source.frameRate) || Number(comp.frameRate) || 0,
                    enabled: layer.enabled !== false,
                    selected: layer.selected === true
                });
            }
            var active = app.project.activeItem;
            if (active && active instanceof CompItem) {
                for (var selectedIndex = 1; selectedIndex <= active.numLayers && items.length < limit; selectedIndex++) {
                    if (active.layer(selectedIndex).selected) { addFootage(active.layer(selectedIndex), active); }
                }
            }
            for (var projectIndex = 1; projectIndex <= app.project.numItems && items.length < limit; projectIndex++) {
                var projectItem = app.project.item(projectIndex);
                if (!(projectItem instanceof CompItem)) { continue; }
                for (var layerIndex = 1; layerIndex <= projectItem.numLayers && items.length < limit; layerIndex++) {
                    addFootage(projectItem.layer(layerIndex), projectItem);
                }
            }
            return response({ok:true,count:items.length,items:items,projectPath:app.project.file ? app.project.file.fsName : ""});
        } catch (error) {
            return response({ok:false,error:error.toString() + (error.line ? " at line " + error.line : "")});
        }
    };

    api.applyReferenceSafeRepair = function (json) {
        var undoStarted = false;
        try {
            var options = parseJSON(json), sourceComp = activeComp(), offset = Math.max(0, Number(options.timelineOffset) || 0);
            var shots = options.shots || [], events = options.events || [];
            if (!shots.length) { throw new Error("The comparison does not contain a reference shot map."); }
            app.beginUndoGroup("TonyFX Safe Reference Repair"); undoStarted = true;
            var repaired = sourceComp.duplicate();
            repaired.name = sourceComp.name + " - TONYFX SAFE REPAIR";
            var scenes = [];
            for (var layerIndex = 1; layerIndex <= repaired.numLayers; layerIndex++) {
                var layer = repaired.layer(layerIndex);
                if (!layer.source || layer.adjustmentLayer || layer.nullLayer || !layer.hasVideo || layer.outPoint <= offset) { continue; }
                scenes.push(layer);
            }
            scenes.sort(function(a,b){ return a.inPoint-b.inPoint || a.index-b.index; });
            var repairedCount = 0, limit = Math.min(shots.length, scenes.length);
            for (var index = 0; index < limit; index++) {
                var scene = scenes[index], shot = shots[index];
                var start = Math.max(0, Math.min(repaired.duration, offset + Number(shot.startTime || 0)));
                var end = Math.max(start + repaired.frameDuration, Math.min(repaired.duration, offset + Number(shot.endTime || start + repaired.frameDuration)));
                scene.inPoint = start; scene.outPoint = end;
                if (options.muteSceneAudio !== false && scene.hasAudio) { scene.audioEnabled = false; }
                repairedCount++;
            }
            var marker = repaired.markerProperty, markerCount = 0;
            for (var eventIndex = 0; eventIndex < events.length; eventIndex++) {
                var event = events[eventIndex], eventTime = offset + Number(event.time || 0);
                if (eventTime < 0 || eventTime > repaired.duration) { continue; }
                var value = new MarkerValue("TonyFX REPAIR | " + String(event.family || "cut").replace(/_/g," ").toUpperCase() + " | " + String(event.graph || "linear") + " | " + String(event.curve || ""));
                try { value.label = 13; } catch (ignoreLabel) {}
                marker.setValueAtTime(eventTime,value); markerCount++;
            }
            repaired.openInViewer();
            app.endUndoGroup(); undoStarted = false;
            return response({ok:true,message:"Created non-destructive repaired comp with " + repairedCount + " shot bounds, muted scene audio, and " + markerCount + " transition instructions.",comp:repaired.name,repaired:repairedCount,markers:markerCount});
        } catch (error) {
            if (undoStarted) { try { app.endUndoGroup(); } catch (ignoreEnd) {} }
            return response({ok:false,error:error.toString() + (error.line ? " at line " + error.line : "")});
        }
    };

    api.renderReferenceCandidateSet = function (json) {
        try {
            var options = parseJSON(json), sourceComp = activeComp(), event = options.event || {};
            var offset = Math.max(0, Number(options.offset) || 0), boundary = offset + Number(event.time || 0);
            var durationFrames = Math.max(3, Number(event.durationFrames) || 5), duration = durationFrames * sourceComp.frameDuration;
            var start = Math.max(0, boundary - duration), end = Math.min(sourceComp.duration, boundary + duration);
            var requested = options.families || [], families = [], seen = {};
            for (var familyIndex = 0; familyIndex < requested.length && families.length < 5; familyIndex++) {
                var familyName = String(requested[familyIndex] || "hard_cut");
                if (!seen[familyName]) { seen[familyName] = true; families.push(familyName); }
            }
            if (!families.length) { families = [String(event.family || "hard_cut")]; }
            function ease(property) {
                try {
                    for (var keyIndex = 1; keyIndex <= property.numKeys; keyIndex++) {
                        var dimensions = property.value instanceof Array ? property.value.length : 1, easeIn = [], easeOut = [];
                        var graph=String(event.graph || "smooth_in_out"),influenceIn=72,influenceOut=72;
                        if(graph==="sharp_start"){influenceIn=keyIndex===1?18:82;influenceOut=keyIndex===1?88:38;}
                        else if(graph==="sharp_end"){influenceIn=keyIndex===property.numKeys?88:38;influenceOut=keyIndex===property.numKeys?18:82;}
                        else if(graph==="speed_ramp"){influenceIn=keyIndex===1?72:94;influenceOut=keyIndex===1?94:27;}
                        for (var dimension = 0; dimension < dimensions; dimension++) { easeIn.push(new KeyframeEase(0,influenceIn)); easeOut.push(new KeyframeEase(0,influenceOut)); }
                        property.setTemporalEaseAtKey(keyIndex,easeIn,easeOut);
                    }
                } catch (ignoreEase) {}
            }
            function sceneAt(comp,timeValue,before) {
                var winner = null, best = 1e9;
                for (var layerIndex = 1; layerIndex <= comp.numLayers; layerIndex++) {
                    var layer = comp.layer(layerIndex);
                    if (!layer.source || layer.adjustmentLayer || layer.nullLayer || !layer.hasVideo || layer.enabled === false) { continue; }
                    var distance = before ? Math.abs(layer.outPoint-timeValue) : Math.abs(layer.inPoint-timeValue);
                    if (layer.inPoint <= timeValue + comp.frameDuration && layer.outPoint >= timeValue - comp.frameDuration && distance < best) { winner=layer; best=distance; }
                }
                return winner;
            }
            function pulseSolid(comp,color,name) {
                var solid=comp.layers.addSolid(color,name,comp.width,comp.height,1,Math.max(comp.frameDuration,end-start));
                solid.startTime=start; solid.inPoint=start; solid.outPoint=end;
                var opacity=solid.property("ADBE Transform Group").property("ADBE Opacity");
                opacity.setValueAtTime(start,0); opacity.setValueAtTime(boundary,100); opacity.setValueAtTime(end,0); ease(opacity);
                return solid;
            }
            function addDirectionalBlur(comp,amount,direction) {
                var adjustment=comp.layers.addSolid([1,1,1],"TONYFX CANDIDATE DIRECTIONAL BLUR",comp.width,comp.height,1,Math.max(comp.frameDuration,end-start));
                adjustment.adjustmentLayer=true; adjustment.startTime=start; adjustment.inPoint=start; adjustment.outPoint=end;
                var effect=null; try { effect=adjustment.property("ADBE Effect Parade").addProperty("ADBE Motion Blur"); } catch (ignoreEffect) {}
                if(effect){ try{effect.property(1).setValue(direction);}catch(ignoreDirection){} var length=null; try{length=effect.property(2);}catch(ignoreLength){} if(length){length.setValueAtTime(start,0);length.setValueAtTime(boundary,amount);length.setValueAtTime(end,0);ease(length);} }
            }
            var outputs=[];
            for (var family = 0; family < families.length; family++) {
                var comp=sourceComp.duplicate(), currentFamily=families[family], outgoing=sceneAt(comp,boundary-comp.frameDuration,true), incoming=sceneAt(comp,boundary+comp.frameDuration,false);
                comp.name="TONYFX CANDIDATE - " + currentFamily.toUpperCase();
                if(currentFamily === "white_flash") { pulseSolid(comp,[1,1,1],"TONYFX CANDIDATE WHITE FLASH"); }
                else if(currentFamily === "black_dip") { pulseSolid(comp,[0,0,0],"TONYFX CANDIDATE BLACK DIP"); }
                else if(currentFamily.indexOf("slide_")===0 || currentFamily.indexOf("whip_")===0) {
                    var directionName=currentFamily.split("_").pop(), dx=0,dy=0;
                    if(directionName==="left")dx=-comp.width; else if(directionName==="right")dx=comp.width; else if(directionName==="up")dy=-comp.height; else dy=comp.height;
                    if(outgoing){var outPos=outgoing.property("ADBE Transform Group").property("ADBE Position"),outBase=outPos.value;outPos.setValueAtTime(start,outBase);outPos.setValueAtTime(end,[outBase[0]+dx,outBase[1]+dy]);ease(outPos);}
                    if(incoming){var inPos=incoming.property("ADBE Transform Group").property("ADBE Position"),inBase=inPos.value;inPos.setValueAtTime(start,[inBase[0]-dx,inBase[1]-dy]);inPos.setValueAtTime(end,inBase);ease(inPos);}
                    addDirectionalBlur(comp,currentFamily.indexOf("whip_")===0?95:58,dx!==0?(dx<0?0:180):(dy<0?90:270));
                } else if(currentFamily.indexOf("zoom")>=0) {
                    var zoomLayer=incoming || outgoing;
                    if(zoomLayer){var scale=zoomLayer.property("ADBE Transform Group").property("ADBE Scale"),baseScale=scale.value,zoomIn=currentFamily.indexOf("out")<0;var factor=zoomIn?1.42:0.76;scale.setValueAtTime(start,[baseScale[0]*factor,baseScale[1]*factor]);scale.setValueAtTime(end,baseScale);ease(scale);}
                    addDirectionalBlur(comp,72,45);
                } else if(currentFamily === "crossfade") {
                    if(outgoing){var outOpacity=outgoing.property("ADBE Transform Group").property("ADBE Opacity");outOpacity.setValueAtTime(start,100);outOpacity.setValueAtTime(end,0);ease(outOpacity);}
                    if(incoming){var inOpacity=incoming.property("ADBE Transform Group").property("ADBE Opacity");inOpacity.setValueAtTime(start,0);inOpacity.setValueAtTime(end,100);ease(inOpacity);}
                } else if(currentFamily === "impact_shake") {
                    var shakeLayer=incoming || outgoing;
                    if(shakeLayer){var shakePos=shakeLayer.property("ADBE Transform Group").property("ADBE Position"),shakeBase=shakePos.value,shakeAmount=Math.max(18,Number(event.forensics&&event.forensics.shake&&event.forensics.shake.amplitudePx||26));shakePos.setValueAtTime(start,shakeBase);shakePos.setValueAtTime(boundary,[shakeBase[0]+shakeAmount,shakeBase[1]-shakeAmount*0.55]);shakePos.setValueAtTime(end,shakeBase);ease(shakePos);}
                    addDirectionalBlur(comp,58,25);
                } else if(currentFamily === "spin_zoom") {
                    var spinLayer=incoming || outgoing;
                    if(spinLayer){var spinScale=spinLayer.property("ADBE Transform Group").property("ADBE Scale"),spinRotation=spinLayer.property("ADBE Transform Group").property("ADBE Rotate Z"),spinBase=spinScale.value,spinDegrees=Number(event.forensics&&event.forensics.transform&&event.forensics.transform.rotation||18),spinRatio=Number(event.forensics&&event.forensics.transform&&event.forensics.transform.scaleRatio||1.35);spinScale.setValueAtTime(start,[spinBase[0]*spinRatio,spinBase[1]*spinRatio]);spinScale.setValueAtTime(end,spinBase);spinRotation.setValueAtTime(start,spinDegrees);spinRotation.setValueAtTime(end,0);ease(spinScale);ease(spinRotation);}
                    addDirectionalBlur(comp,72,45);
                } else if(currentFamily === "perspective_push") {
                    var perspectiveLayer=incoming || outgoing;
                    if(perspectiveLayer){var perspectiveScale=perspectiveLayer.property("ADBE Transform Group").property("ADBE Scale"),perspectivePos=perspectiveLayer.property("ADBE Transform Group").property("ADBE Position"),perspectiveRotation=perspectiveLayer.property("ADBE Transform Group").property("ADBE Rotate Z"),perspectiveBase=perspectiveScale.value,perspectivePoint=perspectivePos.value;perspectiveScale.setValueAtTime(start,[perspectiveBase[0]*1.28,perspectiveBase[1]*0.84]);perspectiveScale.setValueAtTime(end,perspectiveBase);perspectivePos.setValueAtTime(start,[perspectivePoint[0]-comp.width*0.10,perspectivePoint[1]+comp.height*0.04]);perspectivePos.setValueAtTime(end,perspectivePoint);perspectiveRotation.setValueAtTime(start,-8);perspectiveRotation.setValueAtTime(end,0);ease(perspectiveScale);ease(perspectivePos);ease(perspectiveRotation);}
                    addDirectionalBlur(comp,66,12);
                } else if(currentFamily === "mask_wipe") {
                    if(incoming){var masks=incoming.property("ADBE Mask Parade"),mask=masks.addProperty("ADBE Mask Atom"),shape=mask.property("ADBE Mask Shape"),leftShape=new Shape(),rightShape=new Shape();leftShape.vertices=[[0,0],[1,0],[1,comp.height],[0,comp.height]];leftShape.closed=true;rightShape.vertices=[[0,0],[comp.width,0],[comp.width,comp.height],[0,comp.height]];rightShape.closed=true;shape.setValueAtTime(start,leftShape);shape.setValueAtTime(end,rightShape);ease(shape);try{mask.property("ADBE Mask Feather").setValue([24,24]);}catch(ignoreFeather){}}
                } else if(currentFamily === "rgb_split") {
                    var rgbAdjustment=comp.layers.addSolid([1,1,1],"TONYFX CANDIDATE RGB SPLIT",comp.width,comp.height,1,Math.max(comp.frameDuration,end-start));rgbAdjustment.adjustmentLayer=true;rgbAdjustment.startTime=start;rgbAdjustment.inPoint=start;rgbAdjustment.outPoint=end;var channel=null;try{channel=rgbAdjustment.property("ADBE Effect Parade").addProperty("ADBE Channel Blur");}catch(ignoreChannel){}if(channel){for(var channelIndex=1;channelIndex<=Math.min(4,channel.numProperties);channelIndex++){var channelProperty=channel.property(channelIndex);try{channelProperty.setValueAtTime(start,0);channelProperty.setValueAtTime(boundary,channelIndex===2?4:18);channelProperty.setValueAtTime(end,0);ease(channelProperty);}catch(ignoreChannelValue){}}}
                } else if(currentFamily === "directional_smear") {
                    addDirectionalBlur(comp,Math.max(45,Number(event.blurStrength||65)),Number(event.forensics&&event.forensics.flow&&event.forensics.flow.directionDegrees||0));
                }
                var rendered=renderCompositionIntermediate(comp,start,Math.max(comp.frameDuration,end-start),String(options.outputRoot || Folder.myDocuments.fsName + "/TonyFX Local Engine"));
                outputs.push({family:currentFamily,path:rendered.file.fsName,duration:rendered.duration});
                comp.remove();
            }
            return response({ok:true,items:outputs,message:"Rendered " + outputs.length + " real AE transition candidates."});
        } catch (error) {
            return response({ok:false,error:error.toString() + (error.line ? " at line " + error.line : "")});
        }
    };

    api.getInstalledEffectInventory = function () {
        try {
            var effects = app.effects || [], items = [];
            for (var i = 0; i < effects.length; i++) {
                var effect = effects[i] || {};
                items.push({
                    displayName: String(effect.displayName || effect.name || ""),
                    matchName: String(effect.matchName || ""),
                    category: String(effect.category || ""),
                    version: String(effect.version || "")
                });
            }
            return response({ok:true,count:items.length,items:items});
        } catch (error) {
            return response({ok:false,error:error.toString() + (error.line ? " at line " + error.line : "")});
        }
    };

    api.runTool = function (json) {
        try {
            var options = parseJSON(json), comp = activeComp(), layers = selectedLayers(comp), changed = 0, skipped = 0;
            if (options.tool === "motionTile") { return api.applyMotionTileSelected(); }
            if (options.tool === "opacityArch") { return api.applyApprovedOpacitySelected(); }
            if (options.tool === "protect") { return api.toggleProtectSelected(); }
            if (options.tool === "ease") {
                app.beginUndoGroup("TUF Apply Easing"); changed = applyEaseToSelection(comp, options); app.endUndoGroup();
                return response({ok:true,message:options.name + " applied to " + changed + " keyframe(s).",comp:collectSnapshot(comp).comp,guards:collectSnapshot(comp).guards});
            }
            if (options.tool === "pairedWhip") {
                app.beginUndoGroup("TonyFX - " + options.name); changed = applyPairedWhip(comp, layers, options); app.endUndoGroup();
                return response({ok:true,message:options.name + " built across two scene layers.",comp:collectSnapshot(comp).comp,guards:collectSnapshot(comp).guards});
            }
            if (options.tool === "pairedTransition") {
                app.beginUndoGroup("TonyFX - " + options.name); changed = applyPairedTransition(comp, layers, options); app.endUndoGroup();
                return response({ok:true,message:options.name + " built across the selected cut.",comp:collectSnapshot(comp).comp,guards:collectSnapshot(comp).guards});
            }
            if (options.tool === "importMedia") {
                var importFile = new File(options.path); if (!importFile.exists) { throw new Error("Media file not found."); }
                app.beginUndoGroup("TUF Import Media"); var imported = app.project.importFile(new ImportOptions(importFile)); app.endUndoGroup();
                return response({ok:true,message:"Imported " + imported.name + ".",comp:collectSnapshot(comp).comp,guards:collectSnapshot(comp).guards});
            }
            if (!layers.length) { throw new Error("Select one or more layers first."); }
            app.beginUndoGroup("TUF - " + options.name);
            if (options.tool === "applyFfx") {
                var presetFile = new File(options.path); if (!presetFile.exists) { throw new Error("Preset file not found."); }
                for (var f = 0; f < layers.length; f++) { if (!isProtected(layers[f])) { layers[f].applyPreset(presetFile); changed++; } }
            } else if (options.tool === "align") {
                for (var a = 0; a < layers.length; a++) { if (!isProtected(layers[a])) { layers[a].property("ADBE Transform Group").property("ADBE Position").setValue([comp.width / 2, comp.height / 2]); changed++; } }
            } else if (options.tool === "anchor") {
                for (var n = 0; n < layers.length; n++) { if (!isProtected(layers[n])) { var rect = layers[n].sourceRectAtTime(comp.time, false); layers[n].property("ADBE Transform Group").property("ADBE Anchor Point").setValue([rect.left + rect.width / 2, rect.top + rect.height / 2]); changed++; } }
            } else if (options.tool === "sequence") {
                layers.sort(function (x, y) { return x.index - y.index; }); var cursor = comp.time;
                for (var q = 0; q < layers.length; q++) { if (!isProtected(layers[q])) { layers[q].startTime += cursor - layers[q].inPoint; cursor = layers[q].outPoint - comp.frameDuration; changed++; } }
            } else if (options.tool === "reverseOrder") {
                for (var r = 0; r < Math.floor(layers.length / 2); r++) { layers[r].moveAfter(layers[layers.length - 1 - r]); changed++; }
            } else if (options.tool === "trimWorkArea") {
                for (var w = 0; w < layers.length; w++) { if (!isProtected(layers[w])) { layers[w].inPoint = comp.workAreaStart; layers[w].outPoint = comp.workAreaStart + comp.workAreaDuration; changed++; } }
            } else {
                for (var i = 0; i < layers.length; i++) {
                    if (isProtected(layers[i])) { skipped++; continue; }
                    if (options.tool === "layerMotion") { if (applyLayerMotion(comp, layers[i], options, i)) { changed++; } }
                    else if (options.tool === "textMotion") { if (applyTextMotion(comp, layers[i], options, i)) { changed++; } }
                    else if (options.tool === "effect") {
                        if (options.category === "Effects") {
                            var sourceLayer = layers[i];
                            var adjustmentLayer = createEffectAdjustment(comp, options.name, sourceLayer.inPoint, sourceLayer.outPoint, sourceLayer);
                            if (applyEffectPreset(comp, adjustmentLayer, options)) {
                                trimAdjustmentToAnimation(adjustmentLayer, sourceLayer.inPoint, sourceLayer.outPoint);
                                changed++;
                            }
                            else { adjustmentLayer.remove(); }
                        } else if (applyEffectPreset(comp, layers[i], options)) { changed++; }
                    }
                    else if (options.tool === "impactShake") { if (applyImpactShake(comp, layers[i], options)) { changed++; } }
                }
                if (options.tool === "textMotion" && !changed) { throw new Error("Select one or more editable text layers, then apply the Text motion again."); }
                if ((options.tool === "layerMotion" || options.tool === "effect" || options.tool === "impactShake") && !changed) { throw new Error(options.name + " could not be applied to the selected layer type."); }
            }
            app.endUndoGroup();
            var snapshot = collectSnapshot(comp);
            return response({ok:true,message:options.name + " applied to " + changed + " layer(s)." + (skipped ? " Skipped " + skipped + " protected layer(s)." : ""),comp:snapshot.comp,guards:snapshot.guards});
        } catch (error) { try { app.endUndoGroup(); } catch (ignore) {} return response({ok:false,error:error.toString() + (error.line ? " at line " + error.line : "")}); }
    };
    function readTonyFXPayloadFile(filePath) {
        var file=new File(String(filePath || ""));
        if(!file.exists){throw new Error("TonyFX command payload was not found: " + file.fsName);}
        file.encoding="UTF-8";
        if(!file.open("r")){throw new Error("TonyFX could not open the command payload: " + file.fsName);}
        var contents=file.read();file.close();
        if(!contents){throw new Error("TonyFX command payload is empty.");}
        return contents;
    }

    api.buildOfflineEditFromFile = function (filePath) {
        try{return api.buildOfflineEdit(readTonyFXPayloadFile(filePath));}
        catch(error){return response({ok:false,error:error.toString()+(error.line?" at line "+error.line:"")});}
    };

    api.applyReferenceAnalysisMarkersFromFile = function (filePath) {
        try{return api.applyReferenceAnalysisMarkers(readTonyFXPayloadFile(filePath));}
        catch(error){return response({ok:false,error:error.toString()+(error.line?" at line "+error.line:"")});}
    };

    api.applyReferenceSafeRepairFromFile = function (filePath) {
        try{return api.applyReferenceSafeRepair(readTonyFXPayloadFile(filePath));}
        catch(error){return response({ok:false,error:error.toString()+(error.line?" at line "+error.line:"")});}
    };
    api.nativeUIContext = function () {
        try {
            var item = app.project ? app.project.activeItem : null;
            var ids = [], selected = item instanceof CompItem ? item.selectedLayers : [];
            for (var i = 0; i < selected.length; i++) { ids.push(selected[i].id); }
            return response({ok:true,context:{
                aeVersion:String(app.version),
                projectPath:app.project && app.project.file ? app.project.file.fsName : null,
                itemId:item ? item.id : null,
                itemName:item ? item.name : null,
                time:item instanceof CompItem ? item.time : null,
                selectedLayerIds:ids,
                viewerType:app.activeViewer ? String(app.activeViewer.type) : null,
                toolType:app.project ? Number(app.project.toolType) : null
            }});
        } catch (error) { return response({ok:false,error:String(error)}); }
    };
    api.nativeUICapabilities = function () {
        return response({ok:true,protocol:"tonyfx.native-ui.v1",commands:["uiSnapshot","uiActivate","uiClick","uiDoubleClick","uiStroke","uiScroll","uiKey","uiText"],
            observationLifetimeSeconds:120,singleUseObservations:true,exclusiveBridgeOwner:true,
            nativeTarget:"Windows AfterFX.exe only",noAutomaticRetry:true,
            workflow:"Capture uiSnapshot, inspect image, submit one observed action with observationId and expectedContext, then capture a fresh snapshot.",
            limits:["Requires visible foreground AE window for input; uiActivate is explicit.","No guarantee that every AE UI workflow is already implemented or validated.","Native Roto Brush uses observed Layer-panel strokes; external alpha sequences are a different method."]});
    };
}(TUF));
