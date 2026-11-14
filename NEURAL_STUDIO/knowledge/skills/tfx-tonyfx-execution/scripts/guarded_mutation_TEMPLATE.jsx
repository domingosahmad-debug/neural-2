#target aftereffects
/* Copy into task directory, replace ALL placeholders, implement scoped change and
   script-specific verification. Intentionally cannot run as supplied. */
(function(){
    var EXPECTED_PROJECT='__SET_ABSOLUTE_PROJECT__',COMP_ID=-1,COMP_NAME='__SET_COMP_NAME__';
    if(COMP_ID<0 || EXPECTED_PROJECT.indexOf('__SET_')===0)throw new Error('Template is unconfigured');
    if(!app.project.file || app.project.file.fsName!==EXPECTED_PROJECT)throw new Error('Wrong project');
    if(app.project.renderQueue.rendering)throw new Error('Native render is active');
    var c=null;for(var i=1;i<=app.project.numItems;i++){var x=app.project.item(i);if(x.id===COMP_ID)c=x;}
    if(!(c instanceof CompItem)||c.name!==COMP_NAME)throw new Error('Wrong target composition');
    throw new Error('Implement expected layer signature, protected snapshot, scoped changes and report before enabling this template');
    // Wrap actual work in app.beginUndoGroup()/try/finally/app.endUndoGroup().
    // Do not save or change any unrelated composition. Verify before declaring success.
})();
