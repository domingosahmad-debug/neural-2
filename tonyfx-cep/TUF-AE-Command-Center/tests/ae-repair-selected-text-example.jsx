(function(){
var out=new File(Folder.myDocuments.fsName+"/ae-mcp-bridge/tonyfx_selected_text_repair.json"),result={ok:false};
try{
$.evalFile(new File("C:/Users/TUF/AppData/Roaming/Adobe/CEP/extensions/TUF-AE-Command-Center/jsx/host.jsx"));
var comp=app.project&&app.project.activeItem;if(!(comp instanceof CompItem))throw new Error("No active composition.");
var selected=comp.selectedLayers||[];if(selected.length!==1||!selected[0].property("ADBE Text Properties"))throw new Error("Select the single text example layer first.");
var payload='{"id":"text-blur-reveal","name":"Blur Reveal","tool":"textMotion","mode":"blur","unit":"words","duration":11,"smoothness":42}';
result=eval("("+TUF.runTool(payload)+")");result.layer=selected[0].name;result.comp=comp.name;
}catch(error){result={ok:false,error:error.toString(),line:error.line||0};}
out.encoding="UTF-8";if(out.open("w")){out.write(TUF&&TUF.safeStringify?TUF.safeStringify(result):String(result));out.close();}
}());
