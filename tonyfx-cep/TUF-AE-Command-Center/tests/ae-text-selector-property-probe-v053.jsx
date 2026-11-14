(function () {
    var OUT = "C:/Users/TUF/Documents/ae-mcp-bridge/tonyfx_text_selector_probe_v053.txt";
    function write(value) { var f = new File(OUT); f.encoding = "UTF-8"; f.open("w"); f.write(value); f.close(); }
    function walk(group, depth, lines) {
        if (!group) return;
        for (var i = 1; i <= group.numProperties; i++) {
            var p = group.property(i);
            var value = "";
            try { value = p.value instanceof Array ? p.value.join(",") : String(p.value); } catch (_) {}
            lines.push(new Array(depth + 1).join("  ") + i + "\t" + p.name + "\t" + p.matchName + "\t" + value);
            if (p.numProperties) walk(p, depth + 1, lines);
        }
    }
    try {
        var previous = app.project.activeItem;
        var comp = app.project.items.addComp("TONYFX_TEXT_SELECTOR_PROBE_V053", 1080, 1080, 1, 2, 30);
        var layer = comp.layers.addText("TONY FX MOTION");
        var animators = layer.property("ADBE Text Properties").property("ADBE Text Animators");
        var animator = animators.addProperty("ADBE Text Animator");
        animator.name = "TonyFX - Probe";
        var props = animator.property("ADBE Text Animator Properties");
        var candidates = ["ADBE Text Position 3D","ADBE Text Scale 3D","ADBE Text Rotation","ADBE Text Rotation X","ADBE Text Rotation Y","ADBE Text Opacity","ADBE Text Blur","ADBE Text Tracking Amount","ADBE Text Skew","ADBE Text Skew Axis","ADBE Text Anchor Point 3D"];
        for (var c = 0; c < candidates.length; c++) { try { props.addProperty(candidates[c]); } catch (_) {} }
        var selector = animator.property("ADBE Text Selectors").addProperty("ADBE Text Selector");
        var lines = ["AE " + app.version];
        walk(animator, 0, lines);
        comp.remove();
        if (previous && previous instanceof CompItem) previous.openInViewer();
        write(lines.join("\r\n"));
    } catch (e) { write("ERROR\t" + e.toString() + "\tLINE\t" + (e.line || 0)); }
}());
