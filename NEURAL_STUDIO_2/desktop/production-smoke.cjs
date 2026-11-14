(async()=>{
  const until=async predicate=>{const end=Date.now()+10000;while(!predicate()){if(Date.now()>end)throw Error('Desktop readiness deadline');await new Promise(r=>setTimeout(r,30));}};
  await until(()=>token && typeof production==='function');
  const proof={};
  const state=await production('status');
  proof.realProductionEndpoint=Array.isArray(state.jobs) && state.native.integration.includes('TonyFX');
  proof.manualEditorNotOpened=view!=='edit';
  productionButton.click();await until(()=>productionPanel.open && el('production-readiness').textContent);
  proof.crewDialogWorks=productionPanel.open && !!el('production-route');
  proof.exactRoutes=[...el('production-route').options].map(o=>o.value).join(',')==='claude,codex,opencode';
  proof.effortChoice=['default','medium','low','high'].every(v=>[...el('production-effort').options].some(o=>o.value===v));
  el('production-route').value='opencode';el('production-route').dispatchEvent(new Event('change'));
  proof.freeRouteUsesDefaultEffort=el('production-effort').value==='default' && el('production-effort').disabled;
  el('production-route').value='claude';el('production-route').dispatchEvent(new Event('change'));
  proof.subscriptionEffortRestored=el('production-effort').value==='medium' && !el('production-effort').disabled;
  proof.truthfulReadiness=el('production-readiness').textContent.includes('Commissioning');
  proof.writerStatusVisible=el('production-native').textContent.includes('AE writer:');
  el('production-close').click();proof.dialogCloses=!productionPanel.open;
  proof.noUnrequestedModelJobs=(await production('status')).jobs.length===state.jobs.length;
  return proof;
})()
